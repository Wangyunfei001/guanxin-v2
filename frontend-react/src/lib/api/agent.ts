import client from "./client"
import type { Conversation, ConversationDetail, ApiResponse, AgentConfig } from "@/types"

/**
 * Agent API module.
 * Contains Agent configuration and conversation CRUD.
 */
export const agentApi = {
  /**
   * Get the agent runtime configuration (read-only).
   */
  getConfig(): Promise<ApiResponse<AgentConfig>> {
    return client.get("/agent/config")
  },

  updateConfig(
    config: Pick<
      AgentConfig,
      | "model"
      | "temperature"
      | "max_tokens"
      | "system_prompt"
      | "enabled_tools"
      | "enabled_skills"
      | "mcp_servers"
    >,
  ): Promise<ApiResponse<AgentConfig>> {
    return client.put("/agent/config", config)
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
  getConversation(conversationId: string): Promise<ApiResponse<ConversationDetail>> {
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

}
