"use client"

import { create } from "zustand"
import { knowledgeApi } from "@/lib/api/knowledge"
import { describeError } from "@/lib/api/errors"
import type { Document, RetrievalResult } from "@/types"

interface KnowledgeState {
  documents: Document[]
  retrievalResults: RetrievalResult[]
  loading: boolean
  retrieving: boolean
  error: string | null

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
  error: null,

  loadDocuments: async () => {
    set({ loading: true, error: null })
    try {
      const res = await knowledgeApi.listDocuments()
      if (res.code === 0) {
        set({ documents: res.data })
      } else {
        set({ error: res.message || "加载知识库失败" })
      }
    } catch (error) {
      set({ error: describeError(error, "加载知识库失败") })
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
    set({ retrieving: true, error: null })
    try {
      const res = await knowledgeApi.retrieve(query, topK)
      if (res.code === 0) {
        set({ retrievalResults: res.data })
      } else {
        set({ error: res.message || "检索失败" })
      }
    } catch (error) {
      set({ error: describeError(error, "检索失败") })
    } finally {
      set({ retrieving: false })
    }
  },
}))
