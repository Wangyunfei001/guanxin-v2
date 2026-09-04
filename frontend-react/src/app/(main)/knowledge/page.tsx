"use client"

import {
  ArrowsClockwise,
  Database,
  FileText,
  MagnifyingGlass,
  Stack,
  UploadSimple,
} from "@phosphor-icons/react"
import * as React from "react"
import { toast } from "sonner"

import { EmptyState, PageHeader, StatStrip } from "@/components/layout/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { knowledgeApi } from "@/lib/api/knowledge"
import { useKnowledgeStore } from "@/lib/stores/knowledge"
import { useLayoutStore } from "@/lib/stores/layout"
import { formatDate, formatSize } from "@/lib/utils"
import type { Document, DocumentChunk } from "@/types"

const statusTextMap: Record<string, string> = {
  ready: "就绪",
  pending: "等待中",
  failed: "失败",
  parsing: "解析中",
  chunking: "分块中",
  embedding: "嵌入中",
}

function statusClassName(status: string) {
  if (status === "ready") return "border-primary/15 bg-primary/10 text-primary"
  if (status === "failed") return "border-destructive/15 bg-destructive/10 text-destructive"
  if (["parsing", "chunking", "embedding"].includes(status)) {
    return "border-sky-500/15 bg-sky-500/10 text-sky-500"
  }
  return "border-amber-500/15 bg-amber-500/10 text-amber-500"
}

function scoreClassName(score: number) {
  if (score >= 0.8) return "border-primary/15 bg-primary/10 text-primary"
  if (score >= 0.5) return "border-amber-500/15 bg-amber-500/10 text-amber-500"
  return "bg-muted text-muted-foreground"
}

function ChunkList({ chunks }: { chunks: DocumentChunk[] }) {
  if (chunks.length === 0) {
    return <EmptyState icon={Stack} title="暂无切片" description="文档尚未生成可查看的文本切片。" />
  }

  return (
    <div className="space-y-3">
      {chunks.map((chunk, index) => (
        <article key={chunk.chunk_id || index} className="rounded-[12px] border bg-muted/25 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="font-mono text-[10px] text-muted-foreground">CHUNK {index + 1}</span>
            {chunk.score !== undefined && (
              <Badge variant="outline" className={scoreClassName(chunk.score)}>
                {chunk.score.toFixed(2)}
              </Badge>
            )}
          </div>
          <p className="whitespace-pre-wrap break-words text-xs leading-6 text-foreground/85">
            {chunk.content || chunk.text || ""}
          </p>
        </article>
      ))}
    </div>
  )
}

export default function KnowledgePage() {
  const {
    documents,
    retrievalResults,
    loading,
    retrieving,
    loadDocuments,
    uploadDocument,
    deleteDocument,
    retrieve,
  } = useKnowledgeStore()
  const openInspector = useLayoutStore((state) => state.openInspector)
  const [query, setQuery] = React.useState("")
  const [deleteTarget, setDeleteTarget] = React.useState<Document | null>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    loadDocuments()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    toast.loading("正在解析并写入知识库", { id: "upload" })
    const success = await uploadDocument(file, file.name)
    if (success) toast.success("文档已进入知识库", { id: "upload" })
    else toast.error("上传失败", { id: "upload" })
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    const success = await deleteDocument(deleteTarget.doc_id)
    if (success) toast.success("文档已删除")
    else toast.error("删除失败")
    setDeleteTarget(null)
  }

  const handleRetrieve = async () => {
    if (!query.trim()) return
    await retrieve(query, 5)
  }

  const handleViewChunks = async (document: Document) => {
    const toastId = toast.loading("正在读取文档切片")
    try {
      const response = await knowledgeApi.getDocument(document.doc_id)
      if (response.code !== 0) throw new Error(response.message)
      toast.dismiss(toastId)
      openInspector({
        title: document.title,
        description: `${document.chunk_count} 个文本切片 · ${formatSize(document.file_size)}`,
        content: <ChunkList chunks={response.data.chunks || []} />,
      })
    } catch {
      toast.error("获取切片失败", { id: toastId })
    }
  }

  const readyCount = documents.filter((document) => document.status === "ready").length
  const totalChunks = documents.reduce((sum, document) => sum + document.chunk_count, 0)
  const totalSize = documents.reduce((sum, document) => sum + document.file_size, 0)

  return (
    <div className="mx-auto w-full max-w-[1440px] space-y-6 p-4 sm:p-6 lg:p-8">
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept=".pdf,.docx,.txt,.md,.json,.csv,.py,.js,.ts"
        onChange={handleUpload}
      />

      <PageHeader
        eyebrow="KNOWLEDGE"
        title="知识库"
        description="把散落的信息转成可检索、可追溯的租户知识上下文。"
        actions={
          <>
            <Button variant="outline" onClick={() => loadDocuments()}>
              <ArrowsClockwise size={16} />
              刷新
            </Button>
            <Button onClick={() => fileInputRef.current?.click()}>
              <UploadSimple size={16} weight="bold" />
              上传文档
            </Button>
          </>
        }
      />

      <StatStrip
        items={[
          { label: "文档总数", value: documents.length, icon: FileText },
          { label: "就绪文档", value: readyCount, icon: Database, tone: "accent" },
          { label: "文本切片", value: totalChunks, icon: Stack },
          { label: "占用空间", value: formatSize(totalSize), icon: Database },
        ]}
      />

      <Card className="overflow-hidden">
        <CardHeader className="flex-row items-center justify-between border-b">
          <div>
            <CardTitle>文档资源</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">按租户隔离的结构化知识源</p>
          </div>
          {loading && <span className="text-xs text-muted-foreground">正在同步</span>}
        </CardHeader>
        <CardContent className="p-0">
          {documents.length === 0 && !loading ? (
            <EmptyState
              icon={FileText}
              title="知识库还是空的"
              description="上传文本 PDF、DOCX、TXT、Markdown、JSON、CSV 或代码文件，系统会自动解析、切片并建立本地向量索引。"
              action={
                <Button size="sm" onClick={() => fileInputRef.current?.click()}>
                  <UploadSimple size={15} />
                  上传第一份文档
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>文档</TableHead>
                  <TableHead className="hidden md:table-cell">格式</TableHead>
                  <TableHead className="hidden lg:table-cell">大小</TableHead>
                  <TableHead>切片</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="hidden xl:table-cell">创建时间</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((document) => (
                  <TableRow key={document.doc_id}>
                    <TableCell>
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex size-9 shrink-0 items-center justify-center rounded-[10px] bg-muted text-muted-foreground">
                          <FileText size={18} />
                        </div>
                        <div className="min-w-0">
                          <p className="max-w-[240px] truncate text-sm font-medium">{document.title}</p>
                          <p className="mt-0.5 max-w-[240px] truncate text-[11px] text-muted-foreground">
                            {document.filename}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="hidden font-mono text-xs text-muted-foreground md:table-cell">
                      {document.file_type}
                    </TableCell>
                    <TableCell className="hidden text-xs text-muted-foreground lg:table-cell">
                      {formatSize(document.file_size)}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{document.chunk_count}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={statusClassName(document.status)}>
                        {statusTextMap[document.status] || document.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden text-xs text-muted-foreground xl:table-cell">
                      {formatDate(document.created_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => void handleViewChunks(document)}>
                          查看
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground hover:text-destructive"
                          onClick={() => setDeleteTarget(document)}
                        >
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b">
          <CardTitle>检索试验台</CardTitle>
          <p className="text-xs text-muted-foreground">用真实查询快速检查召回质量</p>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <MagnifyingGlass size={16} className="absolute left-3 top-3 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && void handleRetrieve()}
                placeholder="输入问题，例如：如何启动观心？"
                className="pl-9"
              />
            </div>
            <Button onClick={() => void handleRetrieve()} disabled={retrieving || !query.trim()}>
              {retrieving ? "检索中" : "开始检索"}
            </Button>
          </div>

          {retrievalResults.length > 0 && (
            <div className="divide-y rounded-[12px] border">
              {retrievalResults.map((result, index) => (
                <article key={result.chunk_id || index} className="p-4">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[10px] text-muted-foreground">RESULT {index + 1}</span>
                    <Badge variant="outline" className={scoreClassName(result.score)}>
                      相关度 {result.score.toFixed(2)}
                    </Badge>
                    <Badge variant="outline">{result.filename}</Badge>
                  </div>
                  <p className="text-sm leading-6 text-foreground/80">{result.content}</p>
                </article>
              ))}
            </div>
          )}

          {retrievalResults.length === 0 && !retrieving && query && (
            <EmptyState
              icon={MagnifyingGlass}
              title="没有命中内容"
              description="尝试换一种说法，或检查文档是否已经完成向量化。"
              className="min-h-44"
            />
          )}
        </CardContent>
      </Card>

      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除文档</DialogTitle>
          </DialogHeader>
          <p className="text-sm leading-6 text-muted-foreground">
            文档「{deleteTarget?.title}」及其本地文件、切片和向量索引将被永久删除。
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>取消</Button>
            <Button variant="destructive" onClick={() => void handleDelete()}>确认删除</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
