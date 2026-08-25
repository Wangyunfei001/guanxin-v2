"use client";

import { type ReactNode, type FC, useMemo } from "react";
import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useAISDKRuntime } from "@assistant-ui/react-ai-sdk";
import { useChat } from "@ai-sdk/react";
import {
  DefaultChatTransport,
  lastAssistantMessageIsCompleteWithApprovalResponses,
} from "ai";
import type { GuanxinUIMessage } from "@/types";
import { useResearchModeStore } from "@/lib/stores/research";

// ── Provider ──

export const AiSdkRuntimeProvider: FC<{
  children: ReactNode;
  conversationId: string;
  initialMessages?: GuanxinUIMessage[];
}> = ({
  children,
  conversationId,
  initialMessages = [],
}) => {
  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: "/api/agent/chat/aisdk",
        headers: () => {
          const token = window.localStorage.getItem("access_token");
          return token
            ? { Authorization: `Bearer ${token}` }
            : ({} as Record<string, string>);
        },
        fetch: async (input, init) => {
          if (!window.localStorage.getItem("access_token")) {
            throw new Error("登录状态已失效，请重新登录");
          }
          return globalThis.fetch(input, init);
        },
        prepareSendMessagesRequest: ({ id, messages, body }) => ({
          body: {
            ...body,
            id,
            messages,
            research_mode: useResearchModeStore.getState().mode,
          },
        }),
      }),
    [],
  );

  // AI SDK chat hook — connects to our Python backend AI SDK endpoint
  const chatHelpers = useChat<GuanxinUIMessage>({
    id: conversationId,
    messages: initialMessages,
    transport,
    sendAutomaticallyWhen:
      lastAssistantMessageIsCompleteWithApprovalResponses,
  });

  // Bridge AI SDK to assistant-ui runtime.
  // useAISDKRuntime accepts the full ReturnType<typeof useChat>.
  const runtime = useAISDKRuntime(chatHelpers);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
};
