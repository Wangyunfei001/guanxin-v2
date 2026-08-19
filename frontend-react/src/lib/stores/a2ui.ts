"use client"

import { create } from "zustand"
import { a2uiApi } from "@/lib/api/a2ui"
import type { A2UISchema } from "@/types"

interface A2uiState {
  componentTypes: any[]
  templates: any[]
  currentSchema: A2UISchema | null

  loadCatalog: () => Promise<void>
  loadTemplates: () => Promise<void>
  setSchema: (schema: A2UISchema) => void
}

export const useA2uiStore = create<A2uiState>()((set) => ({
  componentTypes: [],
  templates: [],
  currentSchema: null,

  loadCatalog: async () => {
    try {
      const res = await a2uiApi.getCatalog()
      if (res.code === 0) {
        set({ componentTypes: res.data })
      }
    } catch {
      // network error
    }
  },

  loadTemplates: async () => {
    try {
      const res = await a2uiApi.getTemplates()
      if (res.code === 0) {
        set({ templates: res.data })
      }
    } catch {
      // network error
    }
  },

  setSchema: (schema: A2UISchema) => {
    set({ currentSchema: schema })
  },
}))
