"use client"

import { create } from "zustand"
import { mcpApi } from "@/lib/api/mcp"
import { describeError } from "@/lib/api/errors"
import type { MCPConnection, MCPServer, ApiResponse } from "@/types"

interface McpState {
  servers: MCPServer[]
  connections: MCPConnection[]
  loading: boolean
  error: string | null

  loadServers: () => Promise<void>
  loadConnections: () => Promise<void>
  connectServer: (name: string) => Promise<ApiResponse<MCPConnection>>
  callTool: (
    serverName: string,
    toolName: string,
    args: Record<string, any>,
  ) => Promise<ApiResponse<any>>
}

export const useMcpStore = create<McpState>()((set) => ({
  servers: [],
  connections: [],
  loading: false,
  error: null,

  loadServers: async () => {
    set({ loading: true, error: null })
    try {
      const res = await mcpApi.listServers()
      if (res.code === 0) {
        set({ servers: res.data })
      } else {
        set({ error: res.message || "加载 MCP Server 列表失败" })
      }
    } catch (error) {
      set({ error: describeError(error, "加载 MCP Server 列表失败") })
    } finally {
      set({ loading: false })
    }
  },

  loadConnections: async () => {
    try {
      const res = await mcpApi.listConnections()
      if (res.code === 0) {
        set({ connections: res.data })
      } else {
        set({ error: res.message || "加载 MCP 连接失败" })
      }
    } catch (error) {
      set({ error: describeError(error, "加载 MCP 连接失败") })
    }
  },

  connectServer: async (name: string) => {
    return await mcpApi.connectServer(name)
  },

  callTool: async (
    serverName: string,
    toolName: string,
    args: Record<string, any>,
  ) => {
    return await mcpApi.callTool(serverName, toolName, args)
  },
}))
