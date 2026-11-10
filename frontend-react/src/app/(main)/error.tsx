"use client"

import { useEffect } from "react"
import { Button } from "@/components/ui/button"

/**
 * 工作台错误边界。
 *
 * App Router 树里此前没有任何 error boundary：一次坏响应就会让整个
 * 工作台变成 Next 的默认错误页，用户既看不到发生了什么，也没法重试。
 */
export default function MainError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("工作台页面出错", error)
  }, [error])

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <div className="rounded-xl border bg-card px-6 py-5 text-sm text-muted-foreground">
        <p className="text-base font-semibold text-foreground">页面出错了</p>
        <p className="mt-2 max-w-md break-words">{error.message || "未知错误"}</p>
      </div>
      <Button onClick={() => reset()}>重试</Button>
    </div>
  )
}
