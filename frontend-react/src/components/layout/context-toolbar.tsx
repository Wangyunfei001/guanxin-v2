"use client"

import { SignOut, UserCircle } from "@phosphor-icons/react"
import { usePathname, useRouter } from "next/navigation"
import { ThemeToggle } from "@/components/theme/theme-toggle"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuthStore } from "@/lib/stores/auth"
import { CommandMenu } from "./command-menu"
import { pageTitles } from "./navigation-items"

export function ContextToolbar() {
  const pathname = usePathname()
  const router = useRouter()
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)
  const title = pageTitles[pathname] || "观心 v2"

  const handleLogout = () => {
    logout()
    router.push("/login")
  }

  return (
    <header className="relative z-20 flex h-14 shrink-0 items-center justify-between border-b bg-background/92 px-3 backdrop-blur-xl md:px-5">
      <div className="min-w-0 pl-10 md:pl-0">
        <div className="flex items-center gap-2">
          <h1 className="truncate text-[15px] font-semibold tracking-[-0.01em]">{title}</h1>
          {pathname === "/assistant" && (
            <span className="hidden text-xs text-muted-foreground sm:inline">观心助理</span>
          )}
        </div>
      </div>

      <div className="absolute left-1/2 hidden -translate-x-1/2 md:block">
        <CommandMenu />
      </div>

      <div className="flex items-center gap-1.5">
        <div className="md:hidden">
          <CommandMenu />
        </div>
        <ThemeToggle />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-10 gap-2 px-2">
              <Avatar className="size-7">
                <AvatarFallback className="bg-primary/12 text-xs font-semibold text-primary">
                  {(user?.display_name || user?.username || "观").slice(0, 1)}
                </AvatarFallback>
              </Avatar>
              <span className="hidden max-w-28 truncate text-sm sm:inline">
                {user?.display_name || user?.username || "用户"}
              </span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="space-y-1">
              <div>{user?.display_name || user?.username || "用户"}</div>
              <div className="text-xs font-normal text-muted-foreground">
                {user?.tenant_name || "无租户"} · {user?.role || "user"}
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled className="gap-2">
              <UserCircle size={17} />
              账户信息
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleLogout} className="gap-2 text-destructive">
              <SignOut size={17} />
              退出登录
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
