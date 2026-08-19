"use client"

import { useEffect, useState } from "react"
import { redirect } from "next/navigation"
import { useAuthStore } from "@/lib/stores/auth"
import { SideNav } from "@/components/layout/SideNav"
import { Header } from "@/components/layout/Header"

/**
 * Client-side authentication guard.
 * Checks useAuthStore.isLoggedIn; if not logged in, redirects to /login.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const isLoggedIn = useAuthStore((s) => s.isLoggedIn)
  const token = useAuthStore((s) => s.token)
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
      <div className="flex h-screen items-center justify-center">
        <div className="text-muted-foreground">加载中...</div>
      </div>
    )
  }

  if (!isLoggedIn) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-muted-foreground">正在跳转登录页...</div>
      </div>
    )
  }

  return <>{children}</>
}
