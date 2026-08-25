"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

export type ResearchMode = "auto" | "quick" | "deep"

interface ResearchModeState {
  mode: ResearchMode
  setMode: (mode: ResearchMode) => void
}

export const useResearchModeStore = create<ResearchModeState>()(
  persist(
    (set) => ({
      mode: "auto",
      setMode: (mode) => set({ mode }),
    }),
    { name: "guanxin-research-mode" },
  ),
)
