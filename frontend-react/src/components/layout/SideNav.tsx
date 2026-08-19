"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  MessageSquare,
  FileText,
  Zap,
  Bot,
  Plug,
  LayoutGrid,
} from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { href: "/chat", label: "AI 对话", icon: MessageSquare },
  { href: "/knowledge", label: "知识库", icon: FileText },
  { href: "/skills", label: "技能市场", icon: Zap },
  { href: "/agent", label: "Agent 配置", icon: Bot },
  { href: "/mcp", label: "MCP 配置", icon: Plug },
  { href: "/a2ui", label: "A2UI 预览", icon: LayoutGrid },
] as const

/**
 * Side navigation component.
 * Renders the logo and 6 nav menu items with active highlighting.
 */
export function SideNav() {
  const pathname = usePathname()

  return (
    <aside className="flex w-60 flex-col bg-[#001529] text-white">
      <div className="flex h-16 items-center justify-center border-b border-white/10">
        <h2 className="text-lg font-semibold">观心 v2</h2>
      </div>
      <nav className="flex-1 py-4">
        {navItems.map((item) => {
          const isActive = pathname === item.href
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-6 py-3 text-sm transition-colors hover:bg-white/10",
                isActive && "bg-white/15 font-medium"
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
