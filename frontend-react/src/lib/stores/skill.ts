"use client"

import { create } from "zustand"
import { skillApi } from "@/lib/api/skill"
import type { SkillMetadata, ApiResponse } from "@/types"

interface SkillState {
  skills: SkillMetadata[]
  loading: boolean

  loadSkills: () => Promise<void>
  executeSkill: (
    name: string,
    params: Record<string, any>,
  ) => Promise<ApiResponse<any>>
}

export const useSkillStore = create<SkillState>()((set) => ({
  skills: [],
  loading: false,

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

  executeSkill: async (name: string, params: Record<string, any>) => {
    return await skillApi.executeSkill(name, params)
  },
}))
