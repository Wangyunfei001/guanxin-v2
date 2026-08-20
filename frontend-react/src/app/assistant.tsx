"use client";

import { AiSdkRuntimeProvider } from "@/components/assistant-ui/aisdk-runtime-provider";
import { Thread } from "@/components/assistant-ui/thread";
import { Button } from "@/components/ui/button";
import { agentApi } from "@/lib/api/agent";
import type { Conversation, ConversationDetail, GuanxinUIMessage } from "@/types";
import { Menu, MessageSquarePlus, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

const ACTIVE_CONVERSATION_KEY = "guanxin_active_conversation";

export default function Assistant() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [active, setActive] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const selectConversation = useCallback(async (conversationId: string) => {
    const response = await agentApi.getConversation(conversationId);
    if (response.code !== 0 || !response.data) return;
    setActive(response.data);
    localStorage.setItem(ACTIVE_CONVERSATION_KEY, conversationId);
    setDrawerOpen(false);
  }, []);

  const createConversation = useCallback(async () => {
    const response = await agentApi.createConversation();
    if (response.code !== 0) return;
    setConversations((current) => [response.data, ...current]);
    await selectConversation(response.data.conversation_id);
  }, [selectConversation]);

  useEffect(() => {
    let cancelled = false;
    const initialize = async () => {
      try {
        const response = await agentApi.listConversations();
        if (cancelled || response.code !== 0) return;
        const items = response.data || [];
        setConversations(items);
        const savedId = localStorage.getItem(ACTIVE_CONVERSATION_KEY);
        const selected = items.find((item) => item.conversation_id === savedId) || items[0];
        if (selected) {
          await selectConversation(selected.conversation_id);
        } else {
          await createConversation();
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void initialize();
    return () => {
      cancelled = true;
    };
  }, [createConversation, selectConversation]);

  const deleteConversation = async (conversationId: string) => {
    const response = await agentApi.deleteConversation(conversationId);
    if (response.code !== 0) return;
    const remaining = conversations.filter((item) => item.conversation_id !== conversationId);
    setConversations(remaining);
    if (active?.conversation_id === conversationId) {
      setActive(null);
      if (remaining[0]) await selectConversation(remaining[0].conversation_id);
      else await createConversation();
    }
  };

  const initialMessages: GuanxinUIMessage[] = (active?.messages || [])
    .filter((message) => message.role !== "system")
    .map((message) => ({
      id: message.message_id,
      role: message.role as "user" | "assistant",
      parts: message.parts as GuanxinUIMessage["parts"],
    }));

  const sidebar = (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r bg-slate-50">
      <div className="flex items-center justify-between border-b p-3">
        <span className="text-sm font-semibold">会话</span>
        <Button size="icon" variant="ghost" onClick={() => void createConversation()} aria-label="新建会话">
          <MessageSquarePlus className="size-4" />
        </Button>
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto p-2">
        {conversations.map((conversation) => (
          <div
            key={conversation.conversation_id}
            className={`group flex items-center rounded-md text-sm ${
              active?.conversation_id === conversation.conversation_id
                ? "bg-white shadow-sm"
                : "hover:bg-white/70"
            }`}
          >
            <button
              className="min-w-0 flex-1 truncate px-3 py-2 text-left"
              onClick={() => void selectConversation(conversation.conversation_id)}
            >
              {conversation.title || "新对话"}
            </button>
            <Button
              size="icon"
              variant="ghost"
              className="mr-1 size-7 opacity-0 group-hover:opacity-100"
              onClick={() => void deleteConversation(conversation.conversation_id)}
              aria-label="删除会话"
            >
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        ))}
      </div>
    </aside>
  );

  if (loading) {
    return <div className="flex h-[calc(100vh-160px)] items-center justify-center text-sm text-muted-foreground">加载会话中...</div>;
  }

  return (
    <div className="relative -m-2 flex h-[calc(100vh-80px)] overflow-hidden rounded-lg md:-m-6 md:h-[calc(100vh-112px)]">
      <div className="hidden md:block">{sidebar}</div>
      {drawerOpen && (
        <div className="absolute inset-0 z-30 flex md:hidden">
          <div className="relative z-10 h-full">{sidebar}</div>
          <button className="flex-1 bg-black/30" onClick={() => setDrawerOpen(false)} aria-label="关闭会话列表" />
          <Button className="absolute left-[15.5rem] top-2 z-20" size="icon" variant="secondary" onClick={() => setDrawerOpen(false)} aria-label="关闭会话列表">
            <X className="size-4" />
          </Button>
        </div>
      )}
      <section className="relative min-w-0 flex-1 bg-white">
        <Button className="absolute left-3 top-3 z-20 md:hidden" size="icon" variant="outline" onClick={() => setDrawerOpen(true)} aria-label="打开会话列表">
          <Menu className="size-4" />
        </Button>
        {active ? (
          <AiSdkRuntimeProvider
            key={active.conversation_id}
            conversationId={active.conversation_id}
            initialMessages={initialMessages}
          >
            <Thread />
          </AiSdkRuntimeProvider>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">请选择或新建会话</div>
        )}
      </section>
    </div>
  );
}
