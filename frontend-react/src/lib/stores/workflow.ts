"use client"

import { create } from "zustand"
import type { WorkflowStatus } from "@/types"

const ACTIVE = new Set<WorkflowStatus>([
  "planning",
  "running",
  "waiting_input",
  "waiting_approval",
  "uncertain",
])

interface WorkflowUiState {
  statuses: Record<string, WorkflowStatus>
  setStatus: (runId: string, status: WorkflowStatus) => void
  remove: (runId: string) => void
}

export const useWorkflowUiStore = create<WorkflowUiState>()((set) => ({
  statuses: {},
  setStatus: (runId, status) =>
    set((state) => ({ statuses: { ...state.statuses, [runId]: status } })),
  remove: (runId) =>
    set((state) => {
      const statuses = { ...state.statuses }
      delete statuses[runId]
      return { statuses }
    }),
}))

export const selectHasActiveWorkflow = (state: WorkflowUiState) =>
  Object.values(state.statuses).some((status) => ACTIVE.has(status))
