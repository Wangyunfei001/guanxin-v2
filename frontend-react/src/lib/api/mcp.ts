import client from "./client"
import type { MCPConnection, MCPServer, MCPToolPolicy, ApiResponse } from "@/types"

/**
 * MCP (Model Context Protocol) API module.
 * Handles server registration, connection, and tool invocation.
 */
export const mcpApi = {
  /**
   * List all registered MCP servers.
   */
  listServers(): Promise<ApiResponse<MCPServer[]>> {
    return client.get("/mcp/servers")
  },

  /**
   * Register a new MCP server.
   */
  registerServer(data: {
    name: string
    command: string
    args: string[]
    env?: Record<string, string>
    description?: string
  }): Promise<ApiResponse<MCPServer>> {
    return client.post("/mcp/servers", data)
  },

  /**
   * Unregister/delete an MCP server.
   */
  unregisterServer(name: string): Promise<ApiResponse<{ deleted: boolean }>> {
    return client.delete(`/mcp/servers/${name}`)
  },

  /**
   * Connect to an MCP server.
   * May take up to 30s for server startup.
   */
  connectServer(serverName: string): Promise<ApiResponse<MCPConnection>> {
    return client.post(
      "/mcp/connect",
      { server_name: serverName },
      { timeout: 30000 },
    )
  },

  /**
   * List active MCP connections.
   */
  listConnections(): Promise<ApiResponse<MCPConnection[]>> {
    return client.get("/mcp/connections")
  },

  updateToolPolicy(
    serverName: string,
    toolName: string,
    policy: Pick<MCPToolPolicy, "enabled" | "effect" | "approval_required">,
  ): Promise<ApiResponse<MCPToolPolicy>> {
    return client.put(
      `/mcp/servers/${encodeURIComponent(serverName)}/tools/${encodeURIComponent(toolName)}/policy`,
      policy,
    )
  },

  /**
   * Call a tool on a connected MCP server.
   */
  callTool(
    serverName: string,
    toolName: string,
    arguments_: Record<string, any>,
  ): Promise<ApiResponse<any>> {
    return client.post(
      "/mcp/call-tool",
      {
        server_name: serverName,
        tool_name: toolName,
        arguments: arguments_,
      },
      { timeout: 30000 },
    )
  },
}
