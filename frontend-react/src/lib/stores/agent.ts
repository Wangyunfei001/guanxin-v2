"use client"

import { create } from "zustand"
import { skillApi } from "@/lib/api/skill"
import { agentApi } from "@/lib/api/agent"
import { describeError } from "@/lib/api/errors"
import type { SkillMetadata, AgentConfig } from "@/types"

interface AgentState {
  skills: SkillMetadata[]
  loading: boolean
  config: AgentConfig | null
  configLoading: boolean
  saving: boolean
  error: string | null

  loadSkills: () => Promise<void>
  loadConfig: () => Promise<void>
  saveConfig: (config: AgentConfig) => Promise<void>
}

export const useAgentStore = create<AgentState>()((set) => ({
  skills: [],
  loading: false,
  config: null,
  configLoading: false,
  saving: false,
  error: null,

  loadSkills: async () => {
    set({ loading: true, error: null })
    try {
      const res = await skillApi.listSkills()
      if (res.code === 0) {
        set({ skills: res.data })
      } else {
        set({ error: res.message || "加载 Skill 列表失败" })
      }
    } catch (error) {
      set({ error: describeError(error, "加载 Skill 列表失败") })
    } finally {
      set({ loading: false })
    }
  },

  loadConfig: async () => {
    set({ configLoading: true, error: null })
    try {
      const res = await agentApi.getConfig()
      if (res.code === 0) {
        set({ config: res.data })
      } else {
        set({ error: res.message || "加载 Agent 配置失败" })
      }
    } catch (error) {
      set({ error: describeError(error, "加载 Agent 配置失败") })
    } finally {
      set({ configLoading: false })
    }
  },

  saveConfig: async (config) => {
    set({ saving: true })
    try {
      const res = await agentApi.updateConfig(config)
      if (res.code === 0) set({ config: res.data })
    } finally {
      set({ saving: false })
    }
  },
}))
