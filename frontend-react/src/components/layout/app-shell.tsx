"use client"

import { motion, useReducedMotion } from "motion/react"
import { usePathname } from "next/navigation"
import type { ReactNode } from "react"
import { ContextPanel } from "./context-panel"
import { ContextToolbar } from "./context-toolbar"
import { PrimaryRail } from "./primary-rail"

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const reduceMotion = useReducedMotion()

  return (
    <div className="flex h-[100dvh] min-h-[100dvh] overflow-hidden bg-background">
      <PrimaryRail />
      <div className="flex min-w-0 flex-1 flex-col">
        <ContextToolbar />
        <div className="flex min-h-0 flex-1">
          <motion.main
            key={pathname}
            initial={reduceMotion ? false : { opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="min-w-0 flex-1 overflow-auto"
          >
            {children}
          </motion.main>
          <ContextPanel />
        </div>
      </div>
    </div>
  )
}
