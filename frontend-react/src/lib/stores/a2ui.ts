"use client"

import { create } from "zustand"
import { a2uiApi } from "@/lib/api/a2ui"
import { describeError } from "@/lib/api/errors"
import type { A2UISchema } from "@/types"

interface A2uiState {
  componentTypes: any[]
  templates: any[]
  currentSchema: A2UISchema | null
  loading: boolean
  error: string | null

  loadCatalog: () => Promise<void>
  loadTemplates: () => Promise<void>
  setSchema: (schema: A2UISchema) => void
}

export const useA2uiStore = create<A2uiState>()((set) => ({
  componentTypes: [],
  templates: [],
  currentSchema: null,
  loading: false,
  error: null,

  loadCatalog: async () => {
    set({ loading: true, error: null })
    try {
      const res = await a2uiApi.getCatalog()
      if (res.code === 0) {
        set({ componentTypes: res.data })
      } else {
        set({ error: res.message || "加载 A2UI 目录失败" })
      }
    } catch (error) {
      set({ error: describeError(error, "加载 A2UI 目录失败") })
    } finally {
      set({ loading: false })
    }
  },

  loadTemplates: async () => {
    try {
      const res = await a2uiApi.getTemplates()
      if (res.code === 0) {
        set({ templates: res.data })
      } else {
        set({ error: res.message || "加载 A2UI 模板失败" })
      }
    } catch (error) {
      set({ error: describeError(error, "加载 A2UI 模板失败") })
    }
  },

  setSchema: (schema: A2UISchema) => {
    set({ currentSchema: schema })
  },
}))
