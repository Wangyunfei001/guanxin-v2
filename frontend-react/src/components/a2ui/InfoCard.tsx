"use client"

import * as React from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { A2UISchema } from "@/types"

interface InfoItem {
  label: string
  value: any
}

/**
 * InfoCard - displays key-value pairs in a card layout.
 */
export function InfoCard({ schema }: { schema: A2UISchema }) {
  const props = schema.props || {}
  const title = props.title || "信息"
  const content = props.content || ""
  const items: InfoItem[] = props.items || []

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {content && (
          <p className="text-sm text-muted-foreground">{content}</p>
        )}
        {items.length > 0 && (
          <div className="divide-y divide-border rounded-md border">
            {items.map((item, idx) => (
              <div key={idx} className="flex px-3 py-2 text-sm">
                <span className="w-32 shrink-0 font-medium text-muted-foreground">
                  {item.label}
                </span>
                <span className="flex-1 break-words">
                  {String(item.value)}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
