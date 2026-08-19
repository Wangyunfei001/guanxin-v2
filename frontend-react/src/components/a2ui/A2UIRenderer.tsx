"use client"

import * as React from "react"
import type { A2UISchema } from "@/types"
import { FormCard } from "./FormCard"
import { InfoCard } from "./InfoCard"
import { ListCard } from "./ListCard"
import { ConfirmCard } from "./ConfirmCard"
import { ChartCard } from "./ChartCard"

/**
 * A2UI Renderer - dynamic rendering engine.
 *
 * Dispatches based on schema.component_type to the corresponding card component.
 * Falls back to InfoCard for unknown component types.
 * Recursively renders schema.children[] if present.
 */

const componentMap: Record<string, React.FC<{ schema: A2UISchema }>> = {
  form_card: FormCard,
  info_card: InfoCard,
  list_card: ListCard,
  confirm_card: ConfirmCard,
  chart_card: ChartCard,
}

export function A2UIRenderer({ schema }: { schema: A2UISchema }) {
  const Component = componentMap[schema.component_type] ?? InfoCard

  return (
    <div className="a2ui-renderer my-2">
      <Component schema={schema} />
      {schema.children && schema.children.length > 0 && (
        <div className="mt-3">
          {schema.children.map((child, idx) => (
            <A2UIRenderer key={idx} schema={child} />
          ))}
        </div>
      )}
    </div>
  )
}
