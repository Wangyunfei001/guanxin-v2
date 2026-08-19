"use client"

import { create } from "zustand"
import { mcpApi } from "@/lib/api/mcp"
import type { MCPServer, ApiResponse } from "@/types"

interface McpState {
  servers: MCPServer[]
  connections: any[]
  loading: boolean

  loadServers: () => Promise<void>
  loadConnections: () => Promise<void>
  connectServer: (name: string) => Promise<ApiResponse<any>>
  callTool: (
    serverName: string,
    toolName: string,
    args: Record<string, any>,
  ) => Promise<ApiResponse<any>>
}

export const useMcpStore = create<McpState>()((set, get) => ({
  servers: [],
  connections: [],
  loading: false,

  loadServers: async () => {
    set({ loading: true })
    try {
      const res = await mcpApi.listServers()
      if (res.code === 0) {
        set({ servers: res.data })
      }
    } finally {
      set({ loading: false })
    }
  },

  loadConnections: async () => {
    try {
      const res = await mcpApi.listConnections()
      if (res.code === 0) {
        set({ connections: res.data })
      }
    } catch {
      // network error
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
