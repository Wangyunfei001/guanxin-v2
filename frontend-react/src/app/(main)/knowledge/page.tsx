"use client"

import * as React from "react"
import { Upload, RefreshCw, Search, FileText } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { useKnowledgeStore } from "@/lib/stores/knowledge"
import { knowledgeApi } from "@/lib/api/knowledge"
import { formatSize, formatDate } from "@/lib/utils"
import type { Document, DocumentChunk } from "@/types"

const statusColorMap: Record<string, string> = {
  ready: "bg-green-100 text-green-700",
  pending: "bg-orange-100 text-orange-700",
  failed: "bg-red-100 text-red-700",
  parsing: "bg-blue-100 text-blue-700",
  chunking: "bg-blue-100 text-blue-700",
  embedding: "bg-blue-100 text-blue-700",
}

const statusTextMap: Record<string, string> = {
  ready: "就绪",
  pending: "等待中",
  failed: "失败",
  parsing: "解析中",
  chunking: "分块中",
  embedding: "嵌入中",
}

export default function KnowledgePage() {
  const { documents, retrievalResults, loading, retrieving, loadDocuments, uploadDocument, deleteDocument, retrieve } = useKnowledgeStore()
  const [query, setQuery] = React.useState("")
  const [deleteTarget, setDeleteTarget] = React.useState<Document | null>(null)
  const [chunkDoc, setChunkDoc] = React.useState<Document | null>(null)
  const [chunks, setChunks] = React.useState<DocumentChunk[]>([])
  const [loadingChunks, setLoadingChunks] = React.useState(false)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    loadDocuments()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    toast.loading("上传中...", { id: "upload" })
    const success = await uploadDocument(file, file.name)
    if (success) {
      toast.success("上传成功", { id: "upload" })
    } else {
      toast.error("上传失败", { id: "upload" })
    }
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    const success = await deleteDocument(deleteTarget.doc_id)
    if (success) {
      toast.success("删除成功")
    } else {
      toast.error("删除失败")
    }
    setDeleteTarget(null)
  }

  const handleRetrieve = async () => {
    if (!query.trim()) return
    await retrieve(query, 5)
  }

  const handleViewChunks = async (doc: Document) => {
    setChunkDoc(doc)
    setLoadingChunks(true)
    setChunks([])
    try {
      const res = await knowledgeApi.getDocument(doc.doc_id)
      if (res.code === 0 && res.data.chunks) {
        setChunks(res.data.chunks)
      }
    } catch {
      toast.error("获取切片失败")
    } finally {
      setLoadingChunks(false)
    }
  }

  const getScoreClassName = (score: number): string => {
    if (score >= 0.8) return "bg-green-100 text-green-700"
    if (score >= 0.5) return "bg-orange-100 text-orange-700"
    return "bg-gray-100 text-gray-700"
  }

  return (
    <div className="space-y-4">
      {/* Upload + Refresh */}
      <div className="flex gap-2">
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".txt,.md,.json,.csv,.py,.js,.ts"
          onChange={handleUpload}
        />
        <Button onClick={() => fileInputRef.current?.click()}>
          <Upload className="h-4 w-4" />
          上传文档
        </Button>
        <Button variant="outline" onClick={() => loadDocuments()}>
          <RefreshCw className="h-4 w-4" />
          刷新
        </Button>
      </div>

      {/* Document List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">文档列表</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>文档标题</TableHead>
                <TableHead>文件名</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>大小</TableHead>
                <TableHead>分块数</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((doc) => (
                <TableRow key={doc.doc_id}>
                  <TableCell className="font-medium">{doc.title}</TableCell>
                  <TableCell className="text-sm">{doc.filename}</TableCell>
                  <TableCell>{doc.file_type}</TableCell>
                  <TableCell>{formatSize(doc.file_size)}</TableCell>
                  <TableCell>{doc.chunk_count}</TableCell>
                  <TableCell>
                    <Badge
                      variant="secondary"
                      className={statusColorMap[doc.status] || "bg-gray-100"}
                    >
                      {statusTextMap[doc.status] || doc.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDate(doc.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto p-0 text-xs"
                        onClick={() => handleViewChunks(doc)}
                      >
                        查看切片
                      </Button>
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto p-0 text-xs text-red-500"
                        onClick={() => setDeleteTarget(doc)}
                      >
                        删除
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {documents.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground">
                    暂无文档
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Separator />

      {/* Retrieval Test */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">检索测试</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleRetrieve()}
              placeholder="输入查询文本"
              className="flex-1"
            />
            <Button onClick={handleRetrieve} disabled={retrieving}>
              <Search className="h-4 w-4" />
              检索
            </Button>
          </div>

          {retrievalResults.length > 0 && (
            <div className="space-y-2">
              {retrievalResults.map((result, idx) => (
                <div
                  key={result.chunk_id || idx}
                  className="rounded-md border p-3"
                >
                  <div className="mb-1 flex items-center gap-2">
                    <span className="text-xs">片段 {idx + 1}</span>
                    <Badge
                      variant="secondary"
                      className={getScoreClassName(result.score)}
                    >
                      相关度: {result.score.toFixed(2)}
                    </Badge>
                    <Badge variant="secondary" className="bg-blue-100 text-blue-700">
                      {result.filename}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{result.content}</p>
                </div>
              ))}
            </div>
          )}

          {retrievalResults.length === 0 && !retrieving && query && (
            <div className="py-8 text-center text-sm text-muted-foreground">
              暂无检索结果
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确定删除此文档？</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            文档「{deleteTarget?.title}」将被永久删除。
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              删除
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Chunk Preview Dialog */}
      <Dialog open={!!chunkDoc} onOpenChange={(open) => !open && setChunkDoc(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              切片预览: {chunkDoc?.title}
            </DialogTitle>
          </DialogHeader>
          <div className="max-h-96 overflow-y-auto">
            {loadingChunks && (
              <div className="py-8 text-center text-sm text-muted-foreground">
                加载中...
              </div>
            )}
            {!loadingChunks && chunks.length === 0 && (
              <div className="py-8 text-center text-sm text-muted-foreground">
                暂无切片数据
              </div>
            )}
            {!loadingChunks && chunks.map((chunk, idx) => (
              <div key={idx} className="mb-3 rounded-md border p-3">
                <div className="mb-1 flex items-center gap-2">
                  <FileText className="h-3 w-3 text-muted-foreground" />
                  <span className="text-xs font-medium">切片 {idx + 1}</span>
                  {chunk.score !== undefined && (
                    <Badge variant="secondary" className={getScoreClassName(chunk.score)}>
                      {chunk.score.toFixed(2)}
                    </Badge>
                  )}
                </div>
                <p className="text-sm whitespace-pre-wrap break-words text-muted-foreground">
                  {chunk.content || chunk.text || ""}
                </p>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
