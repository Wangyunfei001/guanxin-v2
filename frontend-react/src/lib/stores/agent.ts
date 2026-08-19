"use client"

import { create } from "zustand"
import { skillApi } from "@/lib/api/skill"
import { agentApi } from "@/lib/api/agent"
import type { SkillMetadata, AgentConfig } from "@/types"

interface AgentState {
  skills: SkillMetadata[]
  loading: boolean
  config: AgentConfig | null
  configLoading: boolean
  saving: boolean

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

  loadSkills: async () => {
    set({ loading: true })
    try {
      const res = await skillApi.listSkills()
      if (res.code === 0) {
        set({ skills: res.data })
      }
    } finally {
      set({ loading: false })
    }
  },

  loadConfig: async () => {
    set({ configLoading: true })
    try {
      const res = await agentApi.getConfig()
      if (res.code === 0) {
        set({ config: res.data })
      }
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
