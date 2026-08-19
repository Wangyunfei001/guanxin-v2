"use client"

import * as React from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import type { A2UISchema } from "@/types"

/**
 * ConfirmCard - confirmation card with confirm/cancel buttons.
 * P0: buttons are disabled (display-only mode, consistent with Vue version).
 */
export function ConfirmCard({ schema }: { schema: A2UISchema }) {
  const props = schema.props || {}
  const title = props.title || "确认"
  const message = props.message || ""
  const confirmText = props.confirm_text || "确认"
  const cancelText = props.cancel_text || "取消"
  const danger = props.danger || false

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm">{message}</p>
        <div className="flex gap-2">
          <Button disabled variant={danger ? "destructive" : "default"} size="sm">
            {confirmText}
          </Button>
          <Button disabled variant="outline" size="sm">
            {cancelText}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
