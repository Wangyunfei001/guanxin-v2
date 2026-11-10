import { test, expect } from "@playwright/test"
import { login } from "./helpers"

const output = {
  users: [{ user_id: "usr_1", username: "张三", email: "zhangsan@example.com", role: "admin", status: "active", created_at: "2026-01-15" }],
  total: 7,
  page: 1,
  page_size: 1,
  statistics: { total: 7, roles: { admin: 2, user: 4, viewer: 1 }, statuses: { active: 6, inactive: 1 } },
}

test("users dashboard restores structured tool results on desktop and mobile", async ({ page }) => {
  const errors: string[] = []
  page.on("pageerror", error => errors.push(error.message))
  await page.route("**/api/agent/threads/*/state", async route => {
    const response = await route.fetch()
    const state = await response.json()
    state.values.messages = [
      { type: "human", id: "human-test", content: "查询用户" },
      { type: "ai", id: "call-test", content: "", tool_calls: [{ id: "users-call", name: "skill__query_users", args: {} }] },
      { type: "tool", id: "result-test", name: "skill__query_users", tool_call_id: "users-call", content: JSON.stringify({ success: true, output }) },
      { type: "ai", id: "summary-test", content: "[看板] 以下是系统当前用户列表：共7个用户，活跃6人，非活跃1人。" },
      { type: "human", id: "admin-test", content: "管理员呢" },
      { type: "ai", id: "admin-call", content: "", tool_calls: [{ id: "admin-users-call", name: "skill__query_users", args: { role: "admin" } }] },
      { type: "tool", id: "admin-result", name: "skill__query_users", tool_call_id: "admin-users-call", content: JSON.stringify({ success: true, output }) },
      { type: "ai", id: "advice-test", content: "共 7 位用户，其中 2 位是管理员；非活跃账号建议本周清理。" },
      { type: "human", id: "failed-test", content: "查一下会员" },
      { type: "ai", id: "failed-call", content: "", tool_calls: [{ id: "failed-users-call", name: "skill__query_users", args: { role: "member" } }] },
      { type: "tool", id: "failed-result", name: "skill__query_users", tool_call_id: "failed-users-call", content: JSON.stringify({ success: false, error: "角色筛选不支持 member" }) },
      { type: "ai", id: "failed-reply", content: "[看板] 没有查到用户。" },
      { type: "human", id: "followup-test", content: "你好" },
      { type: "ai", id: "followup-response", content: "你好，有什么可以帮你？" },
    ]
    await route.fulfill({ response, json: state })
  })
  await login(page)
  const dashboards = page.getByRole("region", { name: "用户统计看板" })
  await expect(dashboards).toHaveCount(2)
  const dashboard = dashboards.first()
  await expect(dashboard).toBeVisible()
  // A marked reply that only repeats the dashboard stays hidden.
  await expect(page.getByText("以下是系统当前用户列表：", { exact: false })).toHaveCount(0)
  // A reply that adds advice stays visible.
  await expect(page.getByText("非活跃账号建议本周清理。", { exact: false })).toBeVisible()
  // A failed query keeps its reply, and the marker never reaches the user.
  await expect(page.getByText("没有查到用户。", { exact: false })).toBeVisible()
  await expect(page.getByText("[看板]", { exact: false })).toHaveCount(0)
  await expect(page.getByText("你好，有什么可以帮你？", { exact: true })).toBeVisible()
  await expect(dashboard).toContainText("86%")
  await expect(dashboard).toContainText("4 人 · 57%")
  await dashboard.locator("summary").click()
  await expect(dashboard.getByText("zhangsan@example.com")).toBeVisible()
  await page.screenshot({ path: "output/playwright/users-dashboard-desktop.png", fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(dashboard).toBeVisible()
  await expect(page.getByText("以下是系统当前用户列表：", { exact: false })).toHaveCount(0)
  await expect(page.getByText("非活跃账号建议本周清理。", { exact: false })).toBeVisible()
  await expect(page.getByText("没有查到用户。", { exact: false })).toBeVisible()
  await expect(page.getByText("你好，有什么可以帮你？", { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: "output/playwright/users-dashboard-mobile.png", fullPage: true })
  await page.reload()
  await expect(dashboards).toHaveCount(2)
  await expect(page.getByText("以下是系统当前用户列表：", { exact: false })).toHaveCount(0)
  await expect(page.getByText("非活跃账号建议本周清理。", { exact: false })).toBeVisible()
  await expect(page.getByText("没有查到用户。", { exact: false })).toBeVisible()
  await expect(page.getByText("你好，有什么可以帮你？", { exact: true })).toBeVisible()
  expect(errors).toEqual([])
})
