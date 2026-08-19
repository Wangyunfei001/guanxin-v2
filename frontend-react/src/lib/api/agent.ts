import { baseURL } from "./client"
import client from "./client"
import type { Conversation, ApiResponse, AgentConfig } from "@/types"

/**
 * Agent API module.
 * Contains conversation CRUD + SSE streaming chat.
 */
export const agentApi = {
  /**
   * Get the agent runtime configuration (read-only).
   */
  getConfig(): Promise<ApiResponse<AgentConfig>> {
    return client.get("/agent/config")
  },

  /**
   * Create a new conversation.
   */
  createConversation(
    agentId = "default",
    title = "",
  ): Promise<ApiResponse<Conversation>> {
    return client.post("/agent/conversations", { agent_id: agentId, title })
  },

  /**
   * List all conversations.
   */
  listConversations(): Promise<ApiResponse<Conversation[]>> {
    return client.get("/agent/conversations")
  },

  /**
   * Get a single conversation with messages.
   */
  getConversation(conversationId: string): Promise<ApiResponse<any>> {
    return client.get(`/agent/conversations/${conversationId}`)
  },

  /**
   * Delete a conversation.
   */
  deleteConversation(
    conversationId: string,
  ): Promise<ApiResponse<{ deleted: boolean }>> {
    return client.delete(`/agent/conversations/${conversationId}`)
  },

  /**
   * SSE streaming chat.
   * Uses native fetch (not axios) to get a ReadableStream response.
   * Manually reads token from localStorage for Authorization header.
   *
   * @returns fetch Response object for streamSSE to consume
   */
  async chat(
    conversationId: string,
    message: string,
    options: {
      agentId?: string
      systemPrompt?: string
      enabledTools?: string[]
    } = {},
  ): Promise<Response> {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("access_token") || ""
        : ""

    const response = await fetch(`${baseURL}/agent/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        conversation_id: conversationId,
        message,
        agent_id: options.agentId || "default",
        system_prompt: options.systemPrompt || "",
        enabled_tools: options.enabledTools,
      }),
    })
    return response
  },
}
