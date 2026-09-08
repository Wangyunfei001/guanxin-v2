"use client"

import {
  ArrowClockwise,
  CaretDown,
  CheckCircle,
  Circle,
  Clock,
  Path,
  Prohibit,
  SpinnerGap,
  Warning,
  XCircle,
} from "@phosphor-icons/react"
import { useEffect, useMemo, useState, type FC } from "react"

import { WorkflowControlRenderer } from "./workflow-control"
import { agentApi } from "@/lib/api/agent"
import { useAuthStore } from "@/lib/stores/auth"
import { useWorkflowUiStore } from "@/lib/stores/workflow"
import { cn } from "@/lib/utils"
import type { WorkflowData, WorkflowStep } from "@/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"

const ACTIVE_STATUSES = new Set([
  "planning",
  "running",
  "waiting_input",
  "waiting_approval",
  "uncertain",
])

const STATUS_LABELS: Record<string, string> = {
  planning: "正在规划",
  running: "执行中",
  waiting_input: "等待输入",
  waiting_approval: "等待确认",
  uncertain: "需要人工处理",
  completed: "已完成",
  failed: "执行失败",
  cancelled: "已取消",
  pending: "待执行",
  executing: "执行中",
  waiting_approval_step: "等待确认",
}

const stateTone: Record<string, string> = {
  completed: "text-primary",
  executing: "text-sky-500",
  failed: "text-destructive",
  cancelled: "text-muted-foreground",
  uncertain: "text-amber-500",
  waiting_input: "text-amber-500",
  waiting_approval: "text-amber-500",
  waiting_approval_step: "text-amber-500",
}

const StepIcon: FC<{ step: WorkflowStep }> = ({ step }) => {
  const className = cn("size-[18px]", stateTone[step.status] || "text-muted-foreground/55")
  if (step.status === "completed") return <CheckCircle className={className} weight="fill" />
  if (step.status === "failed") return <XCircle className={className} weight="fill" />
  if (step.status === "cancelled") return <Prohibit className={className} />
  if (step.status === "executing") return <SpinnerGap className={cn(className, "animate-spin")} />
  if (step.status === "uncertain") return <Warning className={className} weight="fill" />
  if (step.status.startsWith("waiting_")) return <Clock className={className} weight="fill" />
  return <Circle className={className} />
}

function statusBadgeVariant(status: string) {
  if (status === "failed") return "destructive" as const
  if (status === "completed") return "default" as const
  return "secondary" as const
}

export const WorkflowDataRenderer: FC<{ data: WorkflowData; onRefresh?: () => void }> = ({ data, onRefresh }) => {
  const [workflow, setWorkflow] = useState<WorkflowData>(data as WorkflowData)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [summary, setSummary] = useState("")
  const isAdmin = useAuthStore((state) => state.isAdmin)
  const setStatus = useWorkflowUiStore((state) => state.setStatus)
  const remove = useWorkflowUiStore((state) => state.remove)

  useEffect(() => setWorkflow(data as WorkflowData), [data])

  useEffect(() => {
    setStatus(workflow.run_id, workflow.status)
  }, [setStatus, workflow.run_id, workflow.status])

  useEffect(() => () => remove(workflow.run_id), [remove, workflow.run_id])

  useEffect(() => {
    if (!ACTIVE_STATUSES.has(workflow.status)) return
    let cancelled = false
    const refresh = async () => {
      try {
        const response = await agentApi.getWorkflow(workflow.run_id)
        if (!cancelled && response.code === 0) setWorkflow(response.data)
      } catch {
        // A transient refresh failure must not erase the persisted snapshot.
      }
    }
    const timer = window.setInterval(() => void refresh(), 1500)
    void refresh()
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [workflow.run_id, workflow.status])

  const completed = useMemo(
    () => workflow.steps.filter((step) => step.status === "completed").length,
    [workflow.steps],
  )

  const progress = workflow.steps.length > 0 ? (completed / workflow.steps.length) * 100 : 0

  const applyAction = async (action: "mark_completed" | "retry" | "cancel") => {
    setBusy(true)
    try {
      const response = workflow.status === "uncertain"
        ? await agentApi.resolveWorkflow(workflow.run_id, action, summary)
        : await agentApi.cancelWorkflow(workflow.run_id)
      if (response.code === 0) { setWorkflow(response.data); onRefresh?.() }
      else setError(response.message)
    } catch (error) {
      setError(error instanceof Error ? error.message : "操作失败，请重试")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      data-slot="workflow-track"
      className="my-4 overflow-hidden rounded-[16px] border border-border/75 bg-card/75 shadow-panel backdrop-blur-sm"
    >
      <header className="border-b px-4 py-4 sm:px-5">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-[11px] bg-primary/10 text-primary">
            <Path size={19} weight="bold" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[11px] font-medium tracking-[0.12em] text-muted-foreground">执行轨迹</p>
              <Badge variant={statusBadgeVariant(workflow.status)} className="rounded-md text-[10px]">
                {STATUS_LABELS[workflow.status] || workflow.status}
              </Badge>
            </div>
            <h3 className="mt-1.5 text-[15px] font-semibold leading-6">{workflow.goal}</h3>
            {workflow.summary && (
              <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{workflow.summary}</p>
            )}
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="font-mono text-[11px] text-muted-foreground">
            {completed}/{workflow.steps.length}
          </span>
        </div>
      </header>

      <div className="px-4 py-3 sm:px-5">
        {workflow.steps.map((step, index) => {
          const openByDefault = step.status !== "completed" && step.status !== "pending"
          const isLast = index === workflow.steps.length - 1
          const current = step.status === "executing" || step.status.startsWith("waiting_") || step.status === "uncertain"

          return (
            <Collapsible key={step.step_id} defaultOpen={openByDefault}>
              <div className="relative flex gap-3">
                <div className="relative flex w-5 shrink-0 justify-center pt-3.5">
                  {!isLast && <span className="absolute bottom-0 top-7 w-px bg-border" />}
                  <span className="relative z-10 bg-card/90">
                    <StepIcon step={step} />
                  </span>
                </div>
                <div
                  className={cn(
                    "mb-2 min-w-0 flex-1 rounded-[12px] border border-transparent transition-colors",
                    current && "border-primary/20 bg-primary/[0.045]",
                    !current && "hover:bg-muted/40",
                  )}
                >
                  <CollapsibleTrigger className="group flex w-full items-center gap-3 px-3 py-3 text-left">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-medium">{step.title}</p>
                      <p className={cn("mt-0.5 text-[11px]", stateTone[step.status] || "text-muted-foreground")}>
                        {STATUS_LABELS[step.status] || step.status}
                      </p>
                    </div>
                    <CaretDown
                      size={14}
                      className="shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-180"
                    />
                  </CollapsibleTrigger>
                  <CollapsibleContent className="px-3 pb-3">
                    <div className="border-t pt-3 text-xs text-muted-foreground">
                      <div className="flex flex-wrap items-center gap-2">
                        <code className="rounded-md bg-muted px-2 py-1 font-mono text-[10px] text-foreground">
                          {step.tool_name}
                        </code>
                        <Badge variant="outline" className="rounded-md px-1.5 py-0 text-[10px]">
                          {step.risk === "write" ? "写操作" : step.risk === "read" ? "只读" : "未知风险"}
                        </Badge>
                        {step.attempt_count > 0 && <span>尝试 {step.attempt_count} 次</span>}
                      </div>
                      {step.error && (
                        <p className="mt-3 rounded-[10px] border border-destructive/20 bg-destructive/5 p-2.5 text-destructive">
                          {step.error}
                        </p>
                      )}
                      {step.result != null && (
                        <pre className="mt-3 max-h-44 overflow-auto whitespace-pre-wrap rounded-[10px] bg-muted/70 p-3 font-mono text-[11px] leading-5 text-foreground">
                          {JSON.stringify(step.result, null, 2)}
                        </pre>
                      )}
                    </div>
                  </CollapsibleContent>
                </div>
              </div>
            </Collapsible>
          )
        })}

        {workflow.last_error && workflow.status !== "completed" && (
          <p className="mt-2 rounded-[10px] border border-destructive/20 bg-destructive/5 p-3 text-xs leading-5 text-destructive">
            {workflow.last_error}
          </p>
        )}

        {workflow.status === "uncertain" && isAdmin && (
          <div className="mt-3 border-t pt-4">
            <label className="mb-2 block text-xs font-medium" htmlFor={`workflow-summary-${workflow.run_id}`}>
              人工处理结果
            </label>
            <Input
              id={`workflow-summary-${workflow.run_id}`}
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              placeholder="填写结果摘要后确认完成"
            />
          </div>
        )}
      </div>

      {error && <p role="alert" className="p-4 text-sm text-destructive">{error}</p>}
      {workflow.pending_interrupt && workflow.pending_interrupt.kind !== "recovery" && (
        <div className="px-4 pt-4" aria-busy={busy}>
          <WorkflowControlRenderer
            key={workflow.pending_interrupt.interrupt_id}
            args={{ ...workflow.pending_interrupt.payload, run_id: workflow.run_id, kind: workflow.pending_interrupt.kind }}
            busy={busy}
            respondToApproval={async ({ approved, reason }) => {
              setBusy(true); setError("")
              try {
                const response = await agentApi.respondWorkflow(workflow.run_id, workflow.pending_interrupt!.interrupt_id, approved, approved && reason ? JSON.parse(reason) : {})
                if (response.code !== 0) throw new Error(response.message)
                setWorkflow(response.data); onRefresh?.()
              } catch (error) { setError(error instanceof Error ? error.message : "操作失败，请重试") }
              finally { setBusy(false) }
            }}
          />
        </div>
      )}
      {ACTIVE_STATUSES.has(workflow.status) && (
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t bg-muted/25 px-4 py-3 sm:px-5">
          <p className="text-[11px] text-muted-foreground">运行 ID {workflow.run_id.slice(0, 8)}</p>
          <div className="flex flex-wrap gap-2">
            {workflow.status === "uncertain" && isAdmin && (
              <>
                <Button
                  size="sm"
                  disabled={busy || !summary.trim()}
                  onClick={() => void applyAction("mark_completed")}
                >
                  确认已完成
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => void applyAction("retry")}
                >
                  <ArrowClockwise size={14} />
                  重新执行
                </Button>
              </>
            )}
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => void applyAction("cancel")}
            >
              取消流程
            </Button>
          </div>
        </footer>
      )}
    </section>
  )
}
