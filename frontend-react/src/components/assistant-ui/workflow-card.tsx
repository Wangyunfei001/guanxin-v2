"use client"

import { useEffect, useMemo, useState, type FC } from "react"
import type { DataMessagePartProps } from "@assistant-ui/react"
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronDown,
  Circle,
  Clock3,
  Loader2,
  RotateCcw,
  XCircle,
} from "lucide-react"

import { agentApi } from "@/lib/api/agent"
import { useAuthStore } from "@/lib/stores/auth"
import { useWorkflowUiStore } from "@/lib/stores/workflow"
import type { WorkflowData, WorkflowStep } from "@/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
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
  planning: "规划中",
  running: "执行中",
  waiting_input: "等待输入",
  waiting_approval: "等待确认",
  uncertain: "需要人工处理",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  pending: "待执行",
  executing: "执行中",
  waiting_approval_step: "等待确认",
}

const StepIcon: FC<{ step: WorkflowStep }> = ({ step }) => {
  if (step.status === "completed") return <CheckCircle2 className="size-4 text-emerald-600" />
  if (step.status === "failed") return <XCircle className="size-4 text-red-600" />
  if (step.status === "cancelled") return <Ban className="size-4 text-slate-400" />
  if (step.status === "executing") return <Loader2 className="size-4 animate-spin text-blue-600" />
  if (step.status === "uncertain") return <AlertTriangle className="size-4 text-amber-600" />
  if (step.status.startsWith("waiting_")) return <Clock3 className="size-4 text-amber-600" />
  return <Circle className="size-4 text-slate-300" />
}

export const WorkflowDataRenderer: FC<DataMessagePartProps<WorkflowData>> = ({ data }) => {
  const [workflow, setWorkflow] = useState<WorkflowData>(data as WorkflowData)
  const [busy, setBusy] = useState(false)
  const [summary, setSummary] = useState("")
  const isAdmin = useAuthStore((state) => state.isAdmin)
  const setStatus = useWorkflowUiStore((state) => state.setStatus)
  const remove = useWorkflowUiStore((state) => state.remove)

  useEffect(() => {
    setWorkflow(data as WorkflowData)
  }, [data])

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

  const applyAction = async (
    action: "mark_completed" | "retry" | "cancel",
  ) => {
    setBusy(true)
    try {
      const response = workflow.status === "uncertain"
        ? await agentApi.resolveWorkflow(workflow.run_id, action, summary)
        : await agentApi.cancelWorkflow(workflow.run_id)
      if (response.code === 0) setWorkflow(response.data)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="my-3 overflow-hidden border-slate-200 bg-slate-50/70 shadow-sm">
      <CardHeader className="space-y-2 border-b bg-white/80 pb-3">
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="text-base">{workflow.goal}</CardTitle>
          <Badge variant={workflow.status === "failed" ? "destructive" : "secondary"}>
            {STATUS_LABELS[workflow.status] || workflow.status}
          </Badge>
        </div>
        {workflow.summary && <p className="text-sm text-muted-foreground">{workflow.summary}</p>}
        <div className="text-xs text-muted-foreground">已完成 {completed}/{workflow.steps.length} 步</div>
      </CardHeader>
      <CardContent className="space-y-2 p-3">
        {workflow.steps.map((step) => (
          <Collapsible key={step.step_id} defaultOpen={step.status !== "completed"}>
            <div className="rounded-md border bg-white px-3 py-2">
              <CollapsibleTrigger className="flex w-full items-center gap-2 text-left">
                <StepIcon step={step} />
                <span className="min-w-0 flex-1 truncate text-sm font-medium">{step.title}</span>
                <span className="text-xs text-muted-foreground">
                  {STATUS_LABELS[step.status] || step.status}
                </span>
                <ChevronDown className="size-3.5 text-muted-foreground" />
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-2 text-xs text-muted-foreground">
                <div className="flex gap-2">
                  <code>{step.tool_name}</code>
                  <Badge variant="outline" className="px-1.5 py-0 text-[10px]">{step.risk}</Badge>
                </div>
                {step.error && <p className="mt-2 text-red-600">{step.error}</p>}
                {step.result != null && (
                  <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-slate-100 p-2">
                    {JSON.stringify(step.result, null, 2)}
                  </pre>
                )}
              </CollapsibleContent>
            </div>
          </Collapsible>
        ))}
        {workflow.last_error && workflow.status !== "completed" && (
          <p className="rounded-md bg-red-50 p-2 text-xs text-red-700">{workflow.last_error}</p>
        )}
        {workflow.status === "uncertain" && isAdmin && (
          <Input
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
            placeholder="确认完成时填写结果摘要"
          />
        )}
      </CardContent>
      {ACTIVE_STATUSES.has(workflow.status) && (
        <CardFooter className="flex flex-wrap gap-2 border-t bg-white/70 py-3">
          {workflow.status === "uncertain" && isAdmin && (
            <>
              <Button size="sm" disabled={busy || !summary.trim()} onClick={() => void applyAction("mark_completed")}>
                确认已完成
              </Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={() => void applyAction("retry")}>
                <RotateCcw className="mr-1 size-3.5" />重新执行
              </Button>
            </>
          )}
          <Button size="sm" variant="outline" disabled={busy} onClick={() => void applyAction("cancel")}>
            取消流程
          </Button>
        </CardFooter>
      )}
    </Card>
  )
}
