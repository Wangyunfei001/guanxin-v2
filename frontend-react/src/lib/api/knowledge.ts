import client from "./client"
import type { Document, DocumentDetail, RetrievalResult, ApiResponse } from "@/types"

/**
 * Knowledge base API module.
 * Handles document upload, list, delete, chunk preview, and retrieval test.
 */
export const knowledgeApi = {
  /**
   * Upload a document file.
   * Uses multipart/form-data with 60s timeout for large files.
   */
  uploadDocument(file: File, title = ""): Promise<ApiResponse<Document>> {
    const formData = new FormData()
    formData.append("file", file)
    if (title) formData.append("title", title)
    return client.post("/knowledge/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60000,
    })
  },

  /**
   * List all documents.
   */
  listDocuments(): Promise<ApiResponse<Document[]>> {
    return client.get("/knowledge/documents")
  },

  /**
   * Get a single document (includes chunks for preview).
   */
  getDocument(docId: string): Promise<ApiResponse<DocumentDetail>> {
    return client.get(`/knowledge/documents/${docId}`)
  },

  /**
   * Delete a document.
   */
  deleteDocument(docId: string): Promise<ApiResponse<{ deleted: boolean }>> {
    return client.delete(`/knowledge/documents/${docId}`)
  },

  /**
   * Retrieve relevant chunks for a query.
   */
  retrieve(query: string, topK = 5): Promise<ApiResponse<RetrievalResult[]>> {
    return client.post("/knowledge/retrieve", { query, top_k: topK })
  },
}
