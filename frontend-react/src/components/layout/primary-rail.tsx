"use client"

import { CaretDoubleLeft, CaretDoubleRight, List, X } from "@phosphor-icons/react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { BrandMark } from "@/components/brand/brand-mark"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { useLayoutStore } from "@/lib/stores/layout"
import { navigationGroups } from "./navigation-items"

function RailContent({ mobile = false }: { mobile?: boolean }) {
  const pathname = usePathname()
  const reduceMotion = useReducedMotion()
  const railExpanded = useLayoutStore((state) => state.railExpanded)
  const toggleRail = useLayoutStore((state) => state.toggleRail)
  const setMobileNavigationOpen = useLayoutStore((state) => state.setMobileNavigationOpen)
  const expanded = mobile || railExpanded

  return (
    <motion.aside
      initial={false}
      animate={{ width: expanded ? 224 : 72 }}
      transition={reduceMotion ? { duration: 0 } : { duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-white/8 bg-[#0d1311] text-[#edf4f1]",
        mobile && "w-56 shadow-float",
      )}
    >
      <div className={cn("flex h-16 items-center", expanded ? "px-4" : "justify-center")}>
        <BrandMark className="text-primary" showWordmark={expanded} />
        {mobile && (
          <Button
            variant="ghost"
            size="icon"
            className="ml-auto size-9 text-[#edf4f1] hover:bg-white/8"
            onClick={() => setMobileNavigationOpen(false)}
            aria-label="关闭导航"
          >
            <X size={18} />
          </Button>
        )}
      </div>

      <TooltipProvider delayDuration={120}>
        <nav className="flex-1 overflow-y-auto px-2 py-2" aria-label="主导航">
          {navigationGroups.map((group, groupIndex) => (
            <div key={group.label} className={cn(groupIndex > 0 && "mt-5")}>
              {expanded && (
                <div className="px-3 pb-2 text-[11px] font-medium tracking-[0.08em] text-[#718078]">
                  {group.label}
                </div>
              )}
              <div className="space-y-1">
                {group.items.map((item) => {
                  const active = pathname === item.href
                  const Icon = item.icon
                  const link = (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => mobile && setMobileNavigationOpen(false)}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group relative flex h-11 items-center rounded-[12px] text-sm transition-colors duration-150",
                        expanded ? "gap-3 px-3" : "justify-center",
                        active
                          ? "bg-primary/12 text-primary"
                          : "text-[#9eada7] hover:bg-white/[0.045] hover:text-[#edf4f1]",
                      )}
                    >
                      {active && (
                        <span className="absolute -left-2 h-5 w-[3px] rounded-r-full bg-primary" />
                      )}
                      <Icon size={20} weight={active ? "fill" : "regular"} />
                      {expanded && <span className="truncate">{item.label}</span>}
                    </Link>
                  )

                  if (expanded) return link
                  return (
                    <Tooltip key={item.href}>
                      <TooltipTrigger asChild>{link}</TooltipTrigger>
                      <TooltipContent side="right" sideOffset={10}>
                        {item.label}
                      </TooltipContent>
                    </Tooltip>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>
      </TooltipProvider>

      {!mobile && (
        <div className="border-t border-white/8 p-2">
          <Button
            variant="ghost"
            className={cn(
              "h-10 w-full text-[#9eada7] hover:bg-white/[0.045] hover:text-[#edf4f1]",
              expanded ? "justify-start px-3" : "px-0",
            )}
            onClick={toggleRail}
            aria-label={expanded ? "折叠导航" : "展开导航"}
          >
            {expanded ? <CaretDoubleLeft size={18} /> : <CaretDoubleRight size={18} />}
            {expanded && <span>折叠导航</span>}
          </Button>
        </div>
      )}
    </motion.aside>
  )
}

export function PrimaryRail() {
  const mobileNavigationOpen = useLayoutStore((state) => state.mobileNavigationOpen)
  const setMobileNavigationOpen = useLayoutStore((state) => state.setMobileNavigationOpen)

  return (
    <>
      <div className="hidden md:block">
        <RailContent />
      </div>
      <AnimatePresence>
        {mobileNavigationOpen && (
          <motion.div
            className="fixed inset-0 z-40 flex md:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              initial={{ x: -32 }}
              animate={{ x: 0 }}
              exit={{ x: -32 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            >
              <RailContent mobile />
            </motion.div>
            <button
              className="flex-1 bg-black/55 backdrop-blur-sm"
              onClick={() => setMobileNavigationOpen(false)}
              aria-label="关闭导航"
            />
          </motion.div>
        )}
      </AnimatePresence>
      <Button
        variant="ghost"
        size="icon"
        className="fixed left-2 top-2 z-30 size-10 md:hidden"
        onClick={() => setMobileNavigationOpen(true)}
        aria-label="打开导航"
      >
        <List size={20} />
      </Button>
    </>
  )
}
