import client from "./client"
import type { Conversation, ConversationDetail, ApiResponse, AgentConfig, ResearchData, WorkflowData } from "@/types"

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

  respondWorkflow(runId: string, interruptId: string, accepted: boolean, values: Record<string, unknown>): Promise<ApiResponse<WorkflowData>> {
    return client.post(`/agent/workflows/${runId}/respond`, { interrupt_id: interruptId, accepted, values })
  },

  getWorkflow(runId: string): Promise<ApiResponse<WorkflowData>> {
    return client.get(`/agent/workflows/${runId}`)
  },

  cancelWorkflow(runId: string): Promise<ApiResponse<WorkflowData>> {
    return client.post(`/agent/workflows/${runId}/cancel`)
  },

  resolveWorkflow(
    runId: string,
    action: "mark_completed" | "retry" | "cancel",
    resultSummary = "",
  ): Promise<ApiResponse<WorkflowData>> {
    return client.post(`/agent/workflows/${runId}/resolve`, {
      action,
      result_summary: resultSummary,
    })
  },

  getResearch(runId: string): Promise<ApiResponse<ResearchData>> {
    return client.get(`/agent/research/${runId}`)
  },

  cancelResearch(runId: string): Promise<ApiResponse<ResearchData>> {
    return client.post(`/agent/research/${runId}/cancel`)
  },

  resumeResearch(runId: string): Promise<ApiResponse<ResearchData>> {
    return client.post(`/agent/research/${runId}/resume`)
  },

}
