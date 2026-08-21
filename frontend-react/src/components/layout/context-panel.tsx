"use client"

import { X } from "@phosphor-icons/react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useLayoutStore } from "@/lib/stores/layout"

export function ContextPanel() {
  const inspector = useLayoutStore((state) => state.inspector)
  const closeInspector = useLayoutStore((state) => state.closeInspector)
  const reduceMotion = useReducedMotion()

  return (
    <AnimatePresence>
      {inspector && (
        <>
          <motion.button
            className="fixed inset-0 z-30 bg-black/45 backdrop-blur-sm xl:hidden"
            onClick={closeInspector}
            aria-label="关闭详情"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.aside
            className="fixed inset-y-0 right-0 z-40 flex w-[min(92vw,360px)] flex-col border-l bg-card shadow-float xl:static xl:z-auto xl:w-80 xl:shadow-none"
            initial={reduceMotion ? false : { x: 28, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={reduceMotion ? { opacity: 0 } : { x: 28, opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.18, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="flex min-h-14 items-start gap-3 border-b px-4 py-3">
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-sm font-semibold">{inspector.title}</h2>
                {inspector.description && (
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    {inspector.description}
                  </p>
                )}
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 shrink-0"
                onClick={closeInspector}
                aria-label="关闭详情"
              >
                <X size={17} />
              </Button>
            </div>
            <ScrollArea className="min-h-0 flex-1">
              <div className="p-4">{inspector.content}</div>
            </ScrollArea>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
