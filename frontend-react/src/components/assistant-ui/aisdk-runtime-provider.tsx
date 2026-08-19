"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
  type FC,
} from "react";
import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useAISDKRuntime } from "@assistant-ui/react-ai-sdk";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import type { A2UISchema } from "@/types";

// ── Chat Send Context (for confirm_action to send follow-up messages) ──

interface ChatSendContextValue {
  sendMessage: (text: string) => void;
}

const ChatSendContext = createContext<ChatSendContextValue>({
  sendMessage: () => {},
});

export const useChatSend = () => useContext(ChatSendContext);

// ── A2UI Context (replaces the old ConfirmFormContext) ──

interface A2UIContextValue {
  a2uiSchemas: A2UISchema[];
  clearSchemas: () => void;
}

const A2UIContext = createContext<A2UIContextValue>({
  a2uiSchemas: [],
  clearSchemas: () => {},
});

export const useA2UI = () => useContext(A2UIContext);

// ── Provider ──

export const AiSdkRuntimeProvider: FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [a2uiSchemas, setA2uiSchemas] = useState<A2UISchema[]>([]);

  const clearSchemas = useCallback(() => setA2uiSchemas([]), []);

  // AI SDK chat hook — connects to our Python backend AI SDK endpoint
  const chatHelpers = useChat({
    transport: new DefaultChatTransport({
      api: "/api/agent/chat/aisdk",
    }),
    onToolCall: ({ toolCall }) => {
      // Accumulate A2UI schemas from data-a2ui tool calls.
      // The tool call name and result contain schema metadata,
      // which will be extracted and added to a2uiSchemas state.
    },
  });

  // Bridge AI SDK to assistant-ui runtime.
  // useAISDKRuntime accepts the full ReturnType<typeof useChat>.
  const runtime = useAISDKRuntime(chatHelpers);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatSendContext.Provider value={{ sendMessage: (text: string) => chatHelpers.sendMessage({ text }) }}>
        <A2UIContext.Provider value={{ a2uiSchemas, clearSchemas }}>
          {children}
        </A2UIContext.Provider>
      </ChatSendContext.Provider>
    </AssistantRuntimeProvider>
  );
};