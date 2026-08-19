"use client"

import * as React from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { A2UISchema } from "@/types"

interface FormField {
  name: string
  label: string
  type: "input" | "select" | "textarea" | "number" | "switch" | string
  required?: boolean
  value?: any
  options?: string[]
}

/**
 * FormCard - renders a form with multiple field types.
 * P0: all fields are disabled (display-only mode).
 *
 * Field types: input, select, textarea, number, switch.
 */
export function FormCard({ schema }: { schema: A2UISchema }) {
  const props = schema.props || {}
  const title = props.title || "表单"
  const fields: FormField[] = props.fields || []
  const submitText = props.submit_text || "提交"

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {fields.map((field, idx) => (
          <div key={idx} className="space-y-1">
            <Label className="text-xs">
              {field.label}
              {field.required && <span className="text-red-500"> *</span>}
            </Label>
            {field.type === "input" && (
              <Input value={field.value || ""} disabled className="h-8 text-sm" />
            )}
            {field.type === "select" && (
              <Select value={field.value || ""} disabled>
                <SelectTrigger className="h-8 text-sm" disabled>
                  <SelectValue placeholder="选择..." />
                </SelectTrigger>
                <SelectContent>
                  {(field.options || []).map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {field.type === "textarea" && (
              <Textarea
                value={field.value || ""}
                rows={3}
                disabled
                className="text-sm"
              />
            )}
            {field.type === "number" && (
              <Input
                type="number"
                value={field.value ?? ""}
                disabled
                className="h-8 text-sm"
              />
            )}
            {field.type === "switch" && (
              <Switch checked={!!field.value} disabled />
            )}
            {!["input", "select", "textarea", "number", "switch"].includes(
              field.type,
            ) && (
              <Input value={field.value || ""} disabled className="h-8 text-sm" />
            )}
          </div>
        ))}
        <Button disabled size="sm">
          {submitText}
        </Button>
      </CardContent>
    </Card>
  )
}
