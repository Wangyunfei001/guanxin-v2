"use client"

import { create } from "zustand"
import { skillApi } from "@/lib/api/skill"
import { describeError } from "@/lib/api/errors"
import type { SkillMetadata, ApiResponse } from "@/types"

interface SkillState {
  skills: SkillMetadata[]
  loading: boolean
  error: string | null

  loadSkills: () => Promise<void>
  executeSkill: (
    name: string,
    params: Record<string, any>,
  ) => Promise<ApiResponse<any>>
}

export const useSkillStore = create<SkillState>()((set) => ({
  skills: [],
  loading: false,
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

  executeSkill: async (name: string, params: Record<string, any>) => {
    return await skillApi.executeSkill(name, params)
  },
}))
