"use client"

import { create } from "zustand"
import { knowledgeApi } from "@/lib/api/knowledge"
import type { Document, RetrievalResult } from "@/types"

interface KnowledgeState {
  documents: Document[]
  retrievalResults: RetrievalResult[]
  loading: boolean
  retrieving: boolean

  loadDocuments: () => Promise<void>
  uploadDocument: (file: File, title?: string) => Promise<boolean>
  deleteDocument: (docId: string) => Promise<boolean>
  retrieve: (query: string, topK?: number) => Promise<void>
}

export const useKnowledgeStore = create<KnowledgeState>()((set, get) => ({
  documents: [],
  retrievalResults: [],
  loading: false,
  retrieving: false,

  loadDocuments: async () => {
    set({ loading: true })
    try {
      const res = await knowledgeApi.listDocuments()
      if (res.code === 0) {
        set({ documents: res.data })
      }
    } finally {
      set({ loading: false })
    }
  },

  uploadDocument: async (file: File, title = "") => {
    try {
      const res = await knowledgeApi.uploadDocument(file, title || file.name)
      if (res.code === 0) {
        await get().loadDocuments()
        return true
      }
      return false
    } catch {
      return false
    }
  },

  deleteDocument: async (docId: string) => {
    try {
      await knowledgeApi.deleteDocument(docId)
      await get().loadDocuments()
      return true
    } catch {
      return false
    }
  },

  retrieve: async (query: string, topK = 5) => {
    set({ retrieving: true })
    try {
      const res = await knowledgeApi.retrieve(query, topK)
      if (res.code === 0) {
        set({ retrievalResults: res.data })
      }
    } finally {
      set({ retrieving: false })
    }
  },
}))
