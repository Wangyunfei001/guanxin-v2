"use client"

import {
  ChatCircleDots,
  ClockCounterClockwise,
  List,
  Plus,
  SidebarSimple,
  Trash,
  X,
} from "@phosphor-icons/react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import { useCallback, useEffect, useMemo, useState } from "react"

import { AiSdkRuntimeProvider } from "@/components/assistant-ui/aisdk-runtime-provider"
import { Thread } from "@/components/assistant-ui/thread"
import { Button } from "@/components/ui/button"
import { agentApi } from "@/lib/api/agent"
import { useLayoutStore } from "@/lib/stores/layout"
import { cn } from "@/lib/utils"
import type { Conversation, ConversationDetail, GuanxinUIMessage } from "@/types"

const ACTIVE_CONVERSATION_KEY = "guanxin_active_conversation"

function formatConversationTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  const today = new Date()
  if (date.toDateString() === today.toDateString()) {
    return new Intl.DateTimeFormat("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date)
  }
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(date)
}

interface ConversationPaneProps {
  activeId?: string
  conversations: Conversation[]
  onCreate: () => void
  onDelete: (conversationId: string) => void
  onSelect: (conversationId: string) => void
}

function ConversationPane({
  activeId,
  conversations,
  onCreate,
  onDelete,
  onSelect,
}: ConversationPaneProps) {
  return (
    <aside className="flex h-full w-[264px] shrink-0 flex-col border-r bg-background lg:bg-muted/30">
      <div className="flex h-16 items-center justify-between border-b px-4">
        <div>
          <p className="text-sm font-semibold">会话流</p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">持续理解，保留上下文</p>
        </div>
        <Button
          size="icon"
          variant="outline"
          className="size-9 rounded-[11px] bg-background"
          onClick={onCreate}
          aria-label="新建会话"
        >
          <Plus size={16} weight="bold" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-2.5">
        {conversations.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-5 text-center">
            <ClockCounterClockwise size={28} className="text-muted-foreground/45" />
            <p className="mt-3 text-sm font-medium">还没有会话</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">新建会话，让观心开始理解你的任务。</p>
          </div>
        ) : (
          <div className="space-y-1">
            {conversations.map((conversation) => {
              const active = activeId === conversation.conversation_id
              return (
                <div
                  key={conversation.conversation_id}
                  className={cn(
                    "group relative flex min-h-14 items-center rounded-[12px] border border-transparent transition-colors",
                    active
                      ? "border-border/70 bg-background shadow-panel"
                      : "hover:bg-background/55",
                  )}
                >
                  {active && <span className="absolute inset-y-3 left-0 w-0.5 rounded-r bg-primary" />}
                  <button
                    className="min-w-0 flex-1 px-3 py-2.5 text-left"
                    onClick={() => onSelect(conversation.conversation_id)}
                  >
                    <span className="block truncate text-[13px] font-medium">
                      {conversation.title || "新对话"}
                    </span>
                    <span className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                      <span>{conversation.message_count || 0} 条消息</span>
                      <span>{formatConversationTime(conversation.updated_at)}</span>
                    </span>
                  </button>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="mr-1.5 size-8 shrink-0 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100 focus-visible:opacity-100"
                    onClick={() => onDelete(conversation.conversation_id)}
                    aria-label="删除会话"
                  >
                    <Trash size={15} />
                  </Button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="border-t px-4 py-3 text-[11px] leading-5 text-muted-foreground">
        会话与工具执行记录会自动保存
      </div>
    </aside>
  )
}

export default function Assistant() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [active, setActive] = useState<ConversationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const reduceMotion = useReducedMotion()
  const openInspector = useLayoutStore((state) => state.openInspector)

  const selectConversation = useCallback(async (conversationId: string) => {
    const response = await agentApi.getConversation(conversationId)
    if (response.code !== 0 || !response.data) return
    setActive(response.data)
    localStorage.setItem(ACTIVE_CONVERSATION_KEY, conversationId)
    setDrawerOpen(false)
  }, [])

  const createConversation = useCallback(async () => {
    const response = await agentApi.createConversation()
    if (response.code !== 0) return
    setConversations((current) => [response.data, ...current])
    await selectConversation(response.data.conversation_id)
  }, [selectConversation])

  useEffect(() => {
    let cancelled = false
    const initialize = async () => {
      try {
        const response = await agentApi.listConversations()
        if (cancelled || response.code !== 0) return
        const items = response.data || []
        setConversations(items)
        const savedId = localStorage.getItem(ACTIVE_CONVERSATION_KEY)
        const selected = items.find((item) => item.conversation_id === savedId) || items[0]
        if (selected) await selectConversation(selected.conversation_id)
        else await createConversation()
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void initialize()
    return () => {
      cancelled = true
    }
  }, [createConversation, selectConversation])

  const deleteConversation = async (conversationId: string) => {
    const response = await agentApi.deleteConversation(conversationId)
    if (response.code !== 0) return
    const remaining = conversations.filter((item) => item.conversation_id !== conversationId)
    setConversations(remaining)
    if (active?.conversation_id === conversationId) {
      setActive(null)
      if (remaining[0]) await selectConversation(remaining[0].conversation_id)
      else await createConversation()
    }
  }

  const initialMessages: GuanxinUIMessage[] = useMemo(
    () =>
      (active?.messages || [])
        .filter((message) => message.role !== "system")
        .map((message) => ({
          id: message.message_id,
          role: message.role as "user" | "assistant",
          parts: message.parts as GuanxinUIMessage["parts"],
        })),
    [active],
  )

  const showInspector = () => {
    if (!active) return
    openInspector({
      title: "会话上下文",
      description: "当前会话的运行边界与持久化状态",
      content: (
        <div className="space-y-6 text-sm">
          <section>
            <p className="text-[11px] font-medium tracking-[0.08em] text-muted-foreground">会话</p>
            <p className="mt-2 font-medium">{active.title || "新对话"}</p>
            <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">{active.conversation_id}</p>
          </section>
          <section className="grid grid-cols-2 gap-2">
            <div className="border-l-2 border-primary pl-3">
              <p className="text-xl font-semibold">{active.messages.length}</p>
              <p className="text-xs text-muted-foreground">历史消息</p>
            </div>
            <div className="border-l-2 border-border pl-3">
              <p className="truncate text-xl font-semibold">{active.agent_id || "默认"}</p>
              <p className="text-xs text-muted-foreground">Agent</p>
            </div>
          </section>
          <section className="space-y-3 border-t pt-5">
            <p className="text-[11px] font-medium tracking-[0.08em] text-muted-foreground">可用上下文</p>
            {["租户知识库", "已启用 Skills", "已连接 MCP", "持久化工作流"].map((item) => (
              <div key={item} className="flex items-center gap-2">
                <span className="size-1.5 rounded-full bg-primary" />
                <span>{item}</span>
              </div>
            ))}
          </section>
        </div>
      ),
    })
  }

  if (loading) {
    return (
      <div className="flex h-full min-h-[420px] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto size-7 animate-spin rounded-full border-2 border-primary/25 border-t-primary" />
          <p className="mt-3 text-sm text-muted-foreground">正在恢复会话流</p>
        </div>
      </div>
    )
  }

  const conversationPane = (
    <ConversationPane
      activeId={active?.conversation_id}
      conversations={conversations}
      onCreate={() => void createConversation()}
      onDelete={(conversationId) => void deleteConversation(conversationId)}
      onSelect={(conversationId) => void selectConversation(conversationId)}
    />
  )

  return (
    <div className="relative flex h-full min-h-[calc(100dvh-3.5rem)] overflow-hidden">
      <div className="hidden lg:block">{conversationPane}</div>

      <AnimatePresence>
        {drawerOpen && (
          <motion.div
            className="fixed inset-0 z-40 flex lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              initial={reduceMotion ? false : { x: -32 }}
              animate={{ x: 0 }}
              exit={reduceMotion ? { opacity: 0 } : { x: -32 }}
              className="relative z-10"
            >
              {conversationPane}
              <Button
                className="absolute left-[272px] top-3 size-9 bg-background shadow-panel"
                size="icon"
                variant="ghost"
                onClick={() => setDrawerOpen(false)}
                aria-label="关闭会话列表"
              >
                <X size={17} />
              </Button>
            </motion.div>
            <button
              className="flex-1 bg-black/55 backdrop-blur-sm"
              onClick={() => setDrawerOpen(false)}
              aria-label="关闭会话列表"
            />
          </motion.div>
        )}
      </AnimatePresence>

      <section className="relative min-w-0 flex-1 overflow-hidden bg-background">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-56 bg-[radial-gradient(circle_at_50%_-30%,hsl(var(--primary)/0.11),transparent_66%)]" />
        <div className="absolute left-3 top-3 z-20 flex gap-1.5 lg:hidden">
          <Button
            size="icon"
            variant="outline"
            className="size-9 bg-background/85 backdrop-blur"
            onClick={() => setDrawerOpen(true)}
            aria-label="打开会话列表"
          >
            <List size={17} />
          </Button>
        </div>
        <div className="absolute right-3 top-3 z-20">
          <Button
            size="sm"
            variant="ghost"
            className="h-9 gap-2 bg-background/70 text-xs text-muted-foreground backdrop-blur hover:text-foreground"
            onClick={showInspector}
            disabled={!active}
          >
            <SidebarSimple size={16} />
            <span className="hidden sm:inline">上下文</span>
          </Button>
        </div>

        {active ? (
          <AiSdkRuntimeProvider
            key={active.conversation_id}
            conversationId={active.conversation_id}
            initialMessages={initialMessages}
          >
            <Thread />
          </AiSdkRuntimeProvider>
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center">
            <div>
              <ChatCircleDots size={34} className="mx-auto text-muted-foreground/40" />
              <p className="mt-4 text-sm font-medium">选择一个会话</p>
              <p className="mt-1 text-xs text-muted-foreground">或新建会话开始任务</p>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
