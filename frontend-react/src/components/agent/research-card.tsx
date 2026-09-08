"use client"

import {
  ArrowSquareOut,
  Binoculars,
  CheckCircle,
  Circle,
  GlobeHemisphereWest,
  PauseCircle,
  Play,
  SpinnerGap,
  XCircle,
} from "@phosphor-icons/react"
import { useEffect, useMemo, useState, type FC } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { agentApi } from "@/lib/api/agent"
import { cn } from "@/lib/utils"
import type { ResearchData, ResearchTask } from "@/types"

const ACTIVE = new Set(["planning", "searching", "analyzing", "synthesizing"])

const STATUS_LABELS: Record<string, string> = {
  planning: "规划问题",
  searching: "检索证据",
  analyzing: "分析缺口",
  synthesizing: "生成报告",
  completed: "研究完成",
  failed: "研究失败",
  cancelled: "已取消",
  interrupted: "等待恢复",
  pending: "待开始",
}

const TaskIcon: FC<{ task: ResearchTask }> = ({ task }) => {
  if (task.status === "completed") return <CheckCircle size={16} weight="fill" className="text-primary" />
  if (task.status === "failed") return <XCircle size={16} weight="fill" className="text-destructive" />
  if (task.status === "searching") return <SpinnerGap size={16} className="animate-spin text-sky-500" />
  return <Circle size={16} className="text-muted-foreground/50" />
}

export const ResearchDataRenderer: FC<{ data: ResearchData }> = ({ data }) => {
  const [research, setResearch] = useState<ResearchData>(data as ResearchData)
  const [busy, setBusy] = useState(false)

  useEffect(() => setResearch(data as ResearchData), [data])

  useEffect(() => {
    if (!ACTIVE.has(research.status)) return
    let stopped = false
    const refresh = async () => {
      try {
        const response = await agentApi.getResearch(research.run_id)
        if (!stopped && response.code === 0) setResearch(response.data)
      } catch {
        // Keep the last persisted snapshot during transient network failures.
      }
    }
    const timer = window.setInterval(() => void refresh(), 1500)
    return () => {
      stopped = true
      window.clearInterval(timer)
    }
  }, [research.run_id, research.status])

  const completedTasks = useMemo(
    () => research.tasks.filter((task) => task.status === "completed").length,
    [research.tasks],
  )
  const progress = research.tasks.length
    ? Math.round((completedTasks / research.tasks.length) * 100)
    : research.status === "completed" ? 100 : 8

  const cancel = async () => {
    setBusy(true)
    try {
      const response = await agentApi.cancelResearch(research.run_id)
      if (response.code === 0) setResearch(response.data)
    } finally {
      setBusy(false)
    }
  }

  const resume = async () => {
    setBusy(true)
    try {
      const response = await agentApi.resumeResearch(research.run_id)
      if (response.code === 0) setResearch(response.data)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="my-4 overflow-hidden rounded-[16px] border border-border/75 bg-card/80 shadow-panel backdrop-blur-sm">
      <header className="border-b px-4 py-4 sm:px-5">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-[11px] bg-sky-500/10 text-sky-600 dark:text-sky-400">
            <Binoculars size={19} weight="bold" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[11px] font-medium tracking-[0.12em] text-muted-foreground">DEEP RESEARCH</p>
              <div className="flex items-center gap-1.5">
                <Badge variant="outline" className="rounded-md text-[10px]">
                  {research.mode === "deep" ? "深度" : "快速"}
                </Badge>
                <Badge
                  variant={research.status === "failed" ? "destructive" : research.status === "completed" ? "default" : "secondary"}
                  className="rounded-md text-[10px]"
                >
                  {STATUS_LABELS[research.status] || research.status}
                </Badge>
              </div>
            </div>
            <h3 className="mt-1.5 text-[15px] font-semibold leading-6">{research.goal}</h3>
            {research.plan?.summary && (
              <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{research.plan.summary}</p>
            )}
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-sky-500 transition-[width] duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="font-mono text-[11px] text-muted-foreground">{progress}%</span>
        </div>
      </header>

      <div className="grid gap-0 md:grid-cols-[minmax(0,1fr)_190px]">
        <div className="space-y-1 px-4 py-3 sm:px-5">
          {research.tasks.length === 0 ? (
            <div className="flex items-center gap-2 py-2 text-xs text-muted-foreground">
              <SpinnerGap size={15} className={cn(ACTIVE.has(research.status) && "animate-spin")} />
              正在生成研究计划
            </div>
          ) : research.tasks.map((task) => (
            <div key={task.task_id} className="flex items-start gap-2.5 rounded-[10px] px-2 py-2 hover:bg-muted/40">
              <span className="mt-0.5"><TaskIcon task={task} /></span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium leading-5">{task.question}</p>
                <p className="text-[10px] text-muted-foreground">
                  {STATUS_LABELS[task.status] || task.status}
                  {task.attempt_count > 0 ? ` · ${task.attempt_count} 次检索` : ""}
                </p>
              </div>
            </div>
          ))}
          {research.error && (
            <p className="mt-2 rounded-[10px] border border-destructive/20 bg-destructive/5 p-3 text-xs text-destructive">
              {research.error}
            </p>
          )}
        </div>

        <aside className="border-t bg-muted/20 px-4 py-4 md:border-l md:border-t-0">
          <div className="flex items-center gap-2 text-xs font-medium">
            <GlobeHemisphereWest size={15} />
            来源与预算
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-[11px]">
            <dt className="text-muted-foreground">来源</dt>
            <dd className="text-right font-mono">{research.sources.length}/{research.budget.max_sources}</dd>
            <dt className="text-muted-foreground">搜索动作</dt>
            <dd className="text-right font-mono">{research.usage.search_actions || 0}/{research.budget.max_searches}</dd>
            <dt className="text-muted-foreground">工具调用</dt>
            <dd className="text-right font-mono">{research.usage.tool_calls || 0}</dd>
          </dl>
          {research.sources.length > 0 && (
            <div className="mt-4 space-y-1.5">
              {research.sources.slice(0, 5).map((source, index) => (
                <a
                  key={source.source_id}
                  href={source.canonical_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-start gap-1.5 rounded-md py-1 text-[11px] leading-4 text-muted-foreground hover:text-foreground"
                >
                  <span className="font-mono text-[9px] text-primary">{index + 1}</span>
                  <span className="line-clamp-2 flex-1">{source.title || source.publisher || source.canonical_url}</span>
                  <ArrowSquareOut size={11} className="mt-0.5 shrink-0" />
                </a>
              ))}
            </div>
          )}
        </aside>
      </div>

      {(ACTIVE.has(research.status) || research.status === "interrupted") && (
        <footer className="flex items-center justify-between gap-3 border-t bg-muted/20 px-4 py-3 sm:px-5">
          <p className="truncate font-mono text-[10px] text-muted-foreground">{research.run_id}</p>
          {research.status === "interrupted" ? (
            <Button size="sm" variant="outline" disabled={busy} onClick={() => void resume()}>
              <Play size={14} weight="fill" />
              恢复
            </Button>
          ) : (
            <Button size="sm" variant="outline" disabled={busy} onClick={() => void cancel()}>
              <PauseCircle size={14} />
              取消研究
            </Button>
          )}
        </footer>
      )}
    </section>
  )
}
