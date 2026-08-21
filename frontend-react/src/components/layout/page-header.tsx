import type { Icon } from "@phosphor-icons/react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

interface PageHeaderProps {
  eyebrow?: string
  title: string
  description: string
  actions?: ReactNode
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <header className="flex flex-col gap-5 border-b pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        {eyebrow && (
          <p className="mb-2 text-[11px] font-medium tracking-[0.14em] text-primary">{eyebrow}</p>
        )}
        <h2 className="text-[28px] font-semibold tracking-[-0.04em] sm:text-[32px]">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

interface StatItem {
  label: string
  value: string | number
  icon?: Icon
  tone?: "default" | "accent" | "warning"
}

export function StatStrip({ items }: { items: StatItem[] }) {
  return (
    <div className="grid overflow-hidden rounded-[14px] border bg-card/55 sm:grid-flow-col sm:auto-cols-fr">
      {items.map((item, index) => {
        const ItemIcon = item.icon
        return (
          <div
            key={item.label}
            className={cn(
              "flex min-h-20 items-center gap-3 px-4 py-3",
              index > 0 && "border-t sm:border-l sm:border-t-0",
            )}
          >
            {ItemIcon && (
              <div
                className={cn(
                  "flex size-9 items-center justify-center rounded-[10px] bg-muted text-muted-foreground",
                  item.tone === "accent" && "bg-primary/10 text-primary",
                  item.tone === "warning" && "bg-amber-500/10 text-amber-500",
                )}
              >
                <ItemIcon size={18} />
              </div>
            )}
            <div>
              <p className="text-xl font-semibold tracking-[-0.03em]">{item.value}</p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">{item.label}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

interface EmptyStateProps {
  icon: Icon
  title: string
  description: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon: EmptyIcon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex min-h-56 flex-col items-center justify-center px-6 text-center", className)}>
      <div className="flex size-12 items-center justify-center rounded-[14px] border bg-muted/35 text-muted-foreground/65">
        <EmptyIcon size={22} />
      </div>
      <p className="mt-4 text-sm font-medium">{title}</p>
      <p className="mt-1 max-w-sm text-xs leading-5 text-muted-foreground">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
