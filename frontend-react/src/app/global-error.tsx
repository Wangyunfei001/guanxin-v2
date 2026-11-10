"use client"

import { useEffect } from "react"

/**
 * 根错误边界。
 *
 * 连根布局本身出错时（layout.tsx 抛异常），error.tsx 不会接管，
 * 只能用 global-error.tsx。
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("应用启动失败", error)
  }, [error])

  return (
    <html lang="zh-CN">
      <body>
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
          <div>
            <p className="text-base font-semibold">应用遇到问题</p>
            <p className="mt-2 max-w-md break-words text-sm text-muted-foreground">
              {error.message || "未知错误"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => reset()}
            className="rounded-lg border px-4 py-2 text-sm font-medium"
          >
            重试
          </button>
        </div>
      </body>
    </html>
  )
}
