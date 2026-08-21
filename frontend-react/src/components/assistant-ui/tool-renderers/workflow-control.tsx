"use client"

import { useMemo, useState, type FC } from "react"
import { ClipboardText as ClipboardPenLine, Warning as AlertTriangle } from "@phosphor-icons/react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface WorkflowField {
  name: string
  label: string
  type: string
  required?: boolean
  default?: unknown
  options?: unknown[]
}

interface WorkflowControlProps {
  args: {
    kind?: "input" | "approval"
    title?: string
    fields?: WorkflowField[]
    tool_name?: string
    arguments?: Record<string, unknown>
    risk?: string
  }
  approval?: { approved?: boolean }
  respondToApproval?: (response: { approved: boolean; reason?: string }) => void
  result?: unknown
}

function coerce(field: WorkflowField, raw: string): unknown {
  if (field.type === "number" || field.type === "integer") return Number(raw)
  if (field.type === "boolean") return raw === "true"
  if (field.type === "array") {
    try {
      return JSON.parse(raw)
    } catch {
      return raw.split(",").map((item) => item.trim()).filter(Boolean)
    }
  }
  return raw
}

export const WorkflowControlRenderer: FC<WorkflowControlProps> = ({
  args,
  approval,
  respondToApproval,
  result,
}) => {
  const fields = useMemo(() => args.fields || [], [args.fields])
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((field) => [field.name, String(field.default ?? "")])),
  )
  const valid = useMemo(
    () => fields.every((field) => !field.required || values[field.name]?.trim()),
    [fields, values],
  )

  if (approval?.approved === false) {
    return <div className="rounded-md bg-muted p-3 text-sm text-muted-foreground">该步骤已拒绝，流程已取消。</div>
  }
  if (result !== undefined) {
    return <div className="rounded-md bg-muted p-3 text-sm text-muted-foreground">响应已提交，工作流正在继续。</div>
  }
  if (approval?.approved === true) {
    return <div className="rounded-md bg-muted p-3 text-sm text-muted-foreground">已确认，正在恢复工作流...</div>
  }

  const needsInput = args.kind === "input"
  return (
    <Card className={needsInput ? "border-blue-200 bg-blue-50/60" : "border-amber-200 bg-amber-50/60"}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          {needsInput ? <ClipboardPenLine className="size-5 text-blue-600" /> : <AlertTriangle className="size-5 text-amber-600" />}
          {args.title || (needsInput ? "补充参数" : "确认工具调用")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {needsInput ? fields.map((field) => (
          <div key={field.name} className="space-y-1">
            <Label>{field.label}{field.required && <span className="text-red-500"> *</span>}</Label>
            {field.options?.length ? (
              <Select value={values[field.name]} onValueChange={(value) => setValues((current) => ({ ...current, [field.name]: value }))}>
                <SelectTrigger><SelectValue placeholder={`选择${field.label}`} /></SelectTrigger>
                <SelectContent>
                  {field.options.map((option) => <SelectItem key={String(option)} value={String(option)}>{String(option)}</SelectItem>)}
                </SelectContent>
              </Select>
            ) : (
              <Input
                type={field.type === "email" ? "email" : "text"}
                value={values[field.name] || ""}
                onChange={(event) => setValues((current) => ({ ...current, [field.name]: event.target.value }))}
                placeholder={field.type === "array" ? "JSON 数组或逗号分隔值" : field.label}
              />
            )}
          </div>
        )) : (
          <div className="space-y-2 text-sm">
            <p>工具：<code>{args.tool_name}</code></p>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded bg-white/70 p-2 text-xs">
              {JSON.stringify(args.arguments || {}, null, 2)}
            </pre>
          </div>
        )}
      </CardContent>
      <CardFooter className="gap-2">
        <Button
          size="sm"
          disabled={needsInput && !valid}
          onClick={() => respondToApproval?.({
            approved: true,
            reason: needsInput
              ? JSON.stringify(Object.fromEntries(fields.map((field) => [field.name, coerce(field, values[field.name] || "")])))
              : "{}",
          })}
        >
          {needsInput ? "提交并继续" : "批准执行"}
        </Button>
        <Button size="sm" variant="outline" onClick={() => respondToApproval?.({ approved: false, reason: "用户取消" })}>
          取消流程
        </Button>
      </CardFooter>
    </Card>
  )
}
