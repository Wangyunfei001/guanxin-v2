"use client"

/**
 * 把任意异常转成可展示的文案。
 *
 * 后端的错误体是 `{code, message, data}`，axios 在非 2xx 时抛出的却是
 * AxiosError；SSE 通道抛的是普通 Error。统一在这里收敛，页面不需要各自
 * 判断异常形状。
 */
export function describeError(error: unknown, fallback = "请求失败，请重试"): string {
  if (typeof error === "string" && error.trim()) return error
  if (error instanceof Error && error.message) return error.message
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message
    if (typeof message === "string" && message) return message
  }
  return fallback
}

/**
 * 统一的登录失效处理。
 *
 * axios 拦截器与 SSE/agent 通道此前各自处理 401：前者跳登录页，后者只
 * 抛错——令牌过期后工作台会永久卡在「登录状态已失效，请重新登录」，
 * 没有任何重新登录的入口。两者现在共用这里。
 */
export function handleUnauthorized(): void {
  if (typeof window === "undefined") return
  localStorage.removeItem("access_token")
  localStorage.removeItem("user_info")
  // 登录页自身返回 401 时不要再跳一次，否则会变成刷新循环。
  if (window.location.pathname.startsWith("/login")) return
  window.location.href = "/login"
}
