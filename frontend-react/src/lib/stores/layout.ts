"use client"

import type { ReactNode } from "react"
import { create } from "zustand"

export interface InspectorPayload {
  title: string
  description?: string
  content: ReactNode
}

interface LayoutState {
  railExpanded: boolean
  mobileNavigationOpen: boolean
  inspector: InspectorPayload | null
  toggleRail: () => void
  setMobileNavigationOpen: (open: boolean) => void
  openInspector: (payload: InspectorPayload) => void
  closeInspector: () => void
}

export const useLayoutStore = create<LayoutState>()((set) => ({
  railExpanded: false,
  mobileNavigationOpen: false,
  inspector: null,
  toggleRail: () => set((state) => ({ railExpanded: !state.railExpanded })),
  setMobileNavigationOpen: (mobileNavigationOpen) => set({ mobileNavigationOpen }),
  openInspector: (inspector) => set({ inspector }),
  closeInspector: () => set({ inspector: null }),
}))
