import client from "./client"
import type { MCPServer, ApiResponse } from "@/types"

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
  connectServer(serverName: string): Promise<ApiResponse<any>> {
    return client.post(
      "/mcp/connect",
      { server_name: serverName },
      { timeout: 30000 },
    )
  },

  /**
   * List active MCP connections.
   */
  listConnections(): Promise<ApiResponse<any[]>> {
    return client.get("/mcp/connections")
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
