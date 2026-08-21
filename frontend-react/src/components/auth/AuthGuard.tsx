"use client"

import { useEffect, useState } from "react"
import { redirect } from "next/navigation"
import { useAuthStore } from "@/lib/stores/auth"

/**
 * Client-side authentication guard.
 * Checks useAuthStore.isLoggedIn; if not logged in, redirects to /login.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const isLoggedIn = useAuthStore((s) => s.isLoggedIn)
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    setHydrated(true)
  }, [])

  useEffect(() => {
    if (hydrated && !isLoggedIn) {
      redirect("/login")
    }
  }, [hydrated, isLoggedIn])

  if (!hydrated) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-background">
        <div className="text-sm text-muted-foreground">正在加载工作台</div>
      </div>
    )
  }

  if (!isLoggedIn) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-background">
        <div className="text-sm text-muted-foreground">正在前往登录页</div>
      </div>
    )
  }

  return <>{children}</>
}
