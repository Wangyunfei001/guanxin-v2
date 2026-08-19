"use client"

import * as React from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import type { A2UISchema } from "@/types"

interface ListColumn {
  key: string
  label: string
  width?: number
}

/**
 * ListCard - renders a table with optional score column coloring.
 * Score badges: >=0.8 green, >=0.5 orange, else default.
 */
export function ListCard({ schema }: { schema: A2UISchema }) {
  const props = schema.props || {}
  const title = props.title || "列表"
  const columns: ListColumn[] = props.columns || []
  const rows: Record<string, any>[] = props.rows || []

  function getScoreVariant(score: string | number): "default" | "secondary" | "destructive" {
    const s = typeof score === "string" ? parseFloat(score) : score
    if (s >= 0.8) return "default"
    if (s >= 0.5) return "secondary"
    return "destructive"
  }

  function getScoreClassName(score: string | number): string {
    const s = typeof score === "string" ? parseFloat(score) : score
    if (s >= 0.8) return "bg-green-100 text-green-700"
    if (s >= 0.5) return "bg-orange-100 text-orange-700"
    return "bg-gray-100 text-gray-700"
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col.key} style={{ width: col.width }}>
                  {col.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, idx) => (
              <TableRow key={idx}>
                {columns.map((col) => {
                  const value = row[col.key]
                  const isScore = col.key === "score"
                  return (
                    <TableCell key={col.key}>
                      {isScore ? (
                        <Badge
                          variant={getScoreVariant(value)}
                          className={getScoreClassName(value)}
                        >
                          {String(value)}
                        </Badge>
                      ) : (
                        <span className="text-sm">{String(value)}</span>
                      )}
                    </TableCell>
                  )
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
