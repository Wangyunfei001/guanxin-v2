"use client"

import { useRouter, usePathname } from "next/navigation"
import { useAuthStore } from "@/lib/stores/auth"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

const pageTitles: Record<string, string> = {
  "/chat": "AI 对话",
  "/knowledge": "知识库管理",
  "/skills": "技能市场",
  "/agent": "Agent 配置",
  "/mcp": "MCP 配置",
  "/a2ui": "A2UI 预览",
}

/**
 * Top header bar.
 * Shows page title on the left, user info + logout on the right.
 */
export function Header() {
  const pathname = usePathname()
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const isAdmin = useAuthStore((s) => s.isAdmin)
  const logout = useAuthStore((s) => s.logout)

  const pageTitle = pageTitles[pathname] || "观心 v2"

  const handleLogout = () => {
    logout()
    router.push("/login")
  }

  return (
    <header className="flex h-16 items-center justify-between border-b bg-white px-6">
      <span className="text-base font-semibold">{pageTitle}</span>
      <div className="flex items-center gap-3">
        <Badge variant={isAdmin ? "destructive" : "default"}>
          {user?.display_name || "未知"} ({user?.role || "user"})
        </Badge>
        <Badge variant="secondary" className="bg-green-100 text-green-700">
          {user?.tenant_name || "无租户"}
        </Badge>
        <Button variant="link" className="text-red-500" onClick={handleLogout}>
          退出
        </Button>
      </div>
    </header>
  )
}
