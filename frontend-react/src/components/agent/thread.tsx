"use client"

import { HttpAgentServerAdapter, useStream } from "@langchain/react"
import { useEffect, useMemo, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { ArrowUp, Stop, DownloadSimple, Paperclip, X } from "@phosphor-icons/react"
import { Button } from "@/components/ui/button"
import { useResearchModeStore, type ResearchMode } from "@/lib/stores/research"
import { selectHasActiveWorkflow, useWorkflowUiStore } from "@/lib/stores/workflow"
import type { HistoricalMessage, WorkflowData, ResearchData } from "@/types"
import { WorkflowDataRenderer } from "./workflow-card"
import { ResearchDataRenderer } from "./research-card"

type AgentState = {
  messages: { type: string; content: unknown; id?: string }[]
  files: Record<string, { content: string | string[] }>
  workflow?: WorkflowData
  research_mode?: ResearchMode
  run_status?: string
  research_review?: { budget: { calls: number; actions: number; max_calls: number; max_actions: number; pending: number; uncertain: number } | null; claims: { claim: string; url: string; quote: string }[] }
  run_error?: string
}

async function authorizedFetch(input: RequestInfo | URL, init?: RequestInit) {
  const token = localStorage.getItem("access_token")
  if (!token) throw new Error("登录状态已失效，请重新登录")
  const headers = new Headers(init?.headers)
  headers.set("Authorization", `Bearer ${token}`)
  const response = await fetch(input, { ...init, headers })
  if (response.status === 401) throw new Error("登录状态已失效，请重新登录")
  return response
}

function textContent(content: unknown): string {
  if (typeof content === "string") return content
  if (!Array.isArray(content)) return ""
  return content.map((block) => typeof block === "string" ? block : block?.type === "text" ? block.text : "").join("")
}

function Markdown({ text }: { text: string }) {
  return <div className="prose prose-sm max-w-none break-words dark:prose-invert [&_pre]:overflow-auto [&_pre]:rounded-lg [&_pre]:bg-muted [&_pre]:p-3 [&_table]:block [&_table]:overflow-auto [&_a]:text-primary"><ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown></div>
}

export function AgentThread(props: { conversationId: string; history: HistoricalMessage[] }) {
  const [revision, setRevision] = useState(0)
  return <NativeThread key={`${props.conversationId}:${revision}`} {...props} refresh={() => setRevision((value) => value + 1)} />
}

function NativeThread({ conversationId, history, refresh }: { conversationId: string; history: HistoricalMessage[]; refresh: () => void }) {
  const transport = useMemo(() => new HttpAgentServerAdapter({
    apiUrl: typeof window === "undefined" ? "http://localhost/api/agent" : `${window.location.origin}/api/agent`,
    threadId: conversationId,
    fetch: authorizedFetch,
  }), [conversationId])
  const stream = useStream<AgentState>({ transport, threadId: conversationId })
  const fileInput = useRef<HTMLInputElement>(null)
  const [attachment, setAttachment] = useState<{ name: string; content: string } | null>(null)
  const [draft, setDraft] = useState("")
  const [actionError, setActionError] = useState("")
  const mode = useResearchModeStore((state) => state.mode)
  const setMode = useResearchModeStore((state) => state.setMode)
  const workflowActive = useWorkflowUiStore(selectHasActiveWorkflow)
  const viewport = useRef<HTMLDivElement>(null)
  const sticky = useRef(true)
  const running = stream.isLoading || stream.values.run_status === "running"
  const disabled = running || stream.isThreadLoading || workflowActive
  useEffect(() => {
    if (sticky.current) viewport.current?.scrollTo({ top: viewport.current.scrollHeight, behavior: "instant" })
  }, [stream.messages, stream.values.workflow])

  const submit = async () => {
    const text = draft.trim()
    if (!text || disabled) return
    setActionError("")
    setDraft("")
    sticky.current = true
    try {
      const content = attachment ? `${text}\n\n附件 ${attachment.name}：\n${attachment.content}` : text
      if (content.length > 100_000) throw new Error("消息和附件合计不能超过 100000 字符")
      await stream.submit({ messages: [{ type: "human", id: crypto.randomUUID(), content }], research_mode: mode })
      setAttachment(null)
    } catch (error) {
      setDraft(text)
      setActionError(error instanceof Error ? error.message : "发送失败，请重试")
    }
  }
  const cancel = async () => {
    setActionError("")
    try {
      const response = await authorizedFetch(`/api/agent/threads/${conversationId}/cancel`, { method: "POST" })
      if (!response.ok) throw new Error("取消失败，请重试")
      await stream.stop({ cancel: false })
      refresh()
    } catch (error) { setActionError(error instanceof Error ? error.message : "取消失败") }
  }
  const download = async (path: string) => {
    try {
      const response = await authorizedFetch(`/api/agent/threads/${conversationId}/files/content?path=${encodeURIComponent(path)}`)
      if (!response.ok) throw new Error("文件暂不可用，请刷新后重试")
      const url = URL.createObjectURL(await response.blob())
      const anchor = document.createElement("a")
      anchor.href = url; anchor.download = path.split("/").pop() || "report.md"; anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) { setActionError(error instanceof Error ? error.message : "下载失败") }
  }
  const parts = stream.messages.length > 0
    ? stream.messages.flatMap((message) => (message.additional_kwargs.legacy_parts || []) as Record<string, any>[])
    : history.flatMap((message) => message.parts)
  const cards = new Map<string, Record<string, any>>()
  for (const part of parts) if ((part.type === "data-research" || part.type === "data-workflow") && part.data?.run_id) cards.set(`${part.type}:${part.data.run_id}`, part)
  const historicalCards = [...cards.values()]
  const error = actionError || (stream.error instanceof Error ? stream.error.message : stream.error ? String(stream.error) : "") || stream.values.run_error

  return <div className="relative flex h-full min-h-[calc(100dvh-3.5rem)] flex-col" data-slot="agent-thread">
    <div ref={viewport} className="min-h-0 flex-1 overflow-y-auto px-4 pt-16 pb-6" onScroll={(event) => { const el = event.currentTarget; sticky.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100 }}>
      <div className="mx-auto max-w-3xl space-y-6" aria-live="polite" aria-busy={running}>
        {stream.isThreadLoading && <p className="text-center text-sm text-muted-foreground">正在恢复会话…</p>}
        {!stream.isThreadLoading && stream.messages.length === 0 && history.length === 0 && <div className="py-24 text-center"><h2 className="text-2xl font-semibold">有什么需要观心协助？</h2><p className="mt-3 text-sm text-muted-foreground">描述任务，查询知识，或开始一项研究。</p></div>}
        {stream.messages.length === 0 && history.map((message) => <article key={message.id} className={message.role === "user" ? "ml-auto w-fit max-w-[90%] rounded-2xl bg-muted px-4 py-3" : "py-2"}><Markdown text={message.parts.filter((part) => part.type === "text").map((part) => part.text).join("")} /></article>)}
        {stream.messages.map((message, index) => {
          const type = message.getType()
          const text = textContent(message.content)
          if (type === "tool") return <details key={message.id || index} className="rounded-xl border bg-card p-3 text-sm"><summary className="cursor-pointer text-muted-foreground">工具结果 · {message.name || "执行结果"}</summary><pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">{text}</pre></details>
          if (type !== "human" && type !== "ai") return null
          return <article key={message.id || index} data-message-role={type} className={type === "human" ? "ml-auto w-fit max-w-[90%] rounded-2xl bg-muted px-4 py-3" : "py-2"}><Markdown text={text} /></article>
        })}
        {stream.toolCalls.length > 0 && <details className="rounded-xl border p-3 text-sm"><summary>工具调用 · {stream.toolCalls.length}</summary>{stream.toolCalls.map((call, index) => <pre key={index} className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(call, null, 2)}</pre>)}</details>}
        {historicalCards.map((part, index) => part.type === "data-research" ? <ResearchDataRenderer key={`research-${index}`} data={part.data as ResearchData} onMigrated={refresh} /> : part.data.run_id !== stream.values.workflow?.run_id ? <WorkflowDataRenderer key={`workflow-${index}`} data={part.data as WorkflowData} onRefresh={refresh} /> : null)}
        {stream.values.workflow && <WorkflowDataRenderer data={stream.values.workflow} onRefresh={refresh} />}
        {Object.keys(stream.values.files || {}).length > 0 && <section className="rounded-xl border bg-card p-4"><h3 className="mb-2 text-sm font-semibold">任务文件</h3>{Object.keys(stream.values.files).map((path) => <Button key={path} variant="ghost" className="flex max-w-full justify-start" onClick={() => void download(path)}><DownloadSimple size={16} /><span className="truncate">{path}</span></Button>)}</section>}
        {running && <p role="status" className="text-sm text-muted-foreground">正在执行任务…</p>}
        {stream.values.research_review?.budget && <section className="rounded-lg border p-4 text-sm" aria-label="研究审查">
          <p>搜索请求 {stream.values.research_review.budget.calls}/{stream.values.research_review.budget.max_calls} · 已报告搜索动作 {stream.values.research_review.budget.actions}/{stream.values.research_review.budget.max_actions}</p>
          <p className="mt-1 text-xs text-muted-foreground">预算按会话累计。动作阈值仅限制后续搜索。</p>
          {!!(stream.values.research_review.budget.pending || stream.values.research_review.budget.uncertain) && <p>搜索进行中或用量待核实，后续搜索已暂停。</p>}
          {stream.values.research_review.claims.map((item, index) => <details key={index} className="mt-3 border-t pt-3">
            <summary className="cursor-pointer">待人工审查：{item.claim}</summary>
            <blockquote className="my-2 border-l-2 pl-3">{item.quote}</blockquote>
            <a href={item.url} target="_blank" rel="noreferrer" className="text-primary underline">查看来源原文</a>
            <p className="mt-1 text-xs text-muted-foreground">摘录已匹配原文；是否支持主张仍需判断。</p>
          </details>)}
        </section>}
        {["interrupted", "failed", "cancelled"].includes(stream.values.run_status || "") && <div className="rounded-lg bg-muted p-3 text-sm"><p>任务已停止，可从已保存的执行状态继续。</p><Button type="button" variant="outline" disabled={disabled} onClick={() => { setActionError(""); void stream.submit(null).catch((error) => setActionError(String(error))) }}>继续任务</Button></div>}
        {error && <p role="alert" className="rounded-lg border border-destructive/30 p-3 text-sm text-destructive">{error}</p>}
      </div>
    </div>
    <form className="mx-auto w-full max-w-3xl shrink-0 px-4 pb-5" onSubmit={(event) => { event.preventDefault(); void submit() }}>
      <div data-slot="agent-composer" className="rounded-[18px] border bg-card p-3 shadow-panel">
        <textarea aria-label="输入消息" placeholder={workflowActive ? "请先处理或取消当前工作流" : "描述任务，或直接问一个问题"} className="min-h-16 w-full resize-none bg-transparent p-2 text-sm outline-none disabled:opacity-50" value={draft} disabled={disabled} onChange={(event) => { setDraft(event.target.value); event.target.style.height = "auto"; event.target.style.height = `${Math.min(event.target.scrollHeight, 176)}px` }} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submit() } }} />
        {attachment && <div className="mb-2 flex items-center gap-2 text-xs"><span>{attachment.name}</span><Button type="button" variant="ghost" size="icon" aria-label="移除附件" disabled={disabled} onClick={() => setAttachment(null)}><X size={14} /></Button></div>}
        <input ref={fileInput} type="file" className="hidden" accept=".txt,.md,.csv,.json,.log" onChange={async (event) => {
          const file = event.target.files?.[0]; event.target.value = ""
          if (!file) return
          if (file.size > 1024 * 1024) { setActionError("文本附件不能超过 1 MB"); return }
          try { setAttachment({ name: file.name, content: await file.text() }); setActionError("") } catch { setActionError("读取附件失败") }
        }} />
        <div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><Button type="button" size="icon" variant="ghost" aria-label="添加文本附件" title="添加 TXT、Markdown、CSV 或 JSON 文本（最多 1 MB）" disabled={disabled} onClick={() => fileInput.current?.click()}><Paperclip size={18} /></Button><select aria-label="研究模式" className="rounded-full border bg-muted px-3 py-1.5 text-xs" value={mode} disabled={disabled} onChange={(event) => setMode(event.target.value as ResearchMode)}><option value="auto">自动</option><option value="quick">快速研究</option><option value="deep">深度研究</option></select></div>{running ? <Button type="button" size="icon" aria-label="停止生成" onClick={() => void cancel()}><Stop size={18} /></Button> : <Button type="submit" size="icon" aria-label="发送消息" disabled={disabled || !draft.trim()}><ArrowUp size={18} /></Button>}</div>
      </div>
      <p className="mt-2 text-center text-[11px] text-muted-foreground">重要操作执行前需要确认，请核查结果与来源。</p>
    </form>
  </div>
}
