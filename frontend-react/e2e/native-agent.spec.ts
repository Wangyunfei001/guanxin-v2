import { test, expect } from "@playwright/test"
import { login } from "./helpers"

test.skip(!process.env.GUANXIN_E2E_AGENT_FIXTURE, "Requires deterministic native model test entrypoint")

test("official SDK streams a Deep Agents report, restores and downloads its file", async ({ page }) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await login(page)
  const previousId = await page.evaluate(() => localStorage.getItem("guanxin_active_conversation"))
  await page.getByRole("button", { name: "新建会话", exact: true }).click()
  await expect.poll(() => page.evaluate(() => localStorage.getItem("guanxin_active_conversation"))).not.toBe(previousId)
  await expect(page.getByLabel("输入消息")).toBeEnabled()
  await page.getByLabel("输入消息").fill("生成测试报告")
  await page.getByLabel("发送消息").click()
  await expect.poll(async () => {
    const { id, token } = await page.evaluate(() => ({ id: localStorage.getItem("guanxin_active_conversation"), token: localStorage.getItem("access_token") }))
    const state = await page.request.get(`/api/agent/threads/${id}/state`, { headers: { Authorization: `Bearer ${token}` } })
    const values = (await state.json()).values
    return { status: values.run_status, error: values.run_error, files: Object.keys(values.files || {}) }
  }).toEqual({ status: "completed", error: "", files: ["/reports/browser.md"] })
  await expect(page.getByRole("button", { name: "/reports/browser.md", exact: true })).toBeVisible()
  await expect(page.locator('[data-message-role="ai"]').filter({ hasText: "测试报告已保存" })).toBeVisible()
  await expect(page.getByLabel("输入消息")).toBeEnabled()
  const downloadEvent = page.waitForEvent("download")
  await page.getByRole("button", { name: "/reports/browser.md", exact: true }).click()
  const download = await downloadEvent
  expect(download.suggestedFilename()).toBe("browser.md")
  await page.reload()
  await expect(page.getByRole("button", { name: "/reports/browser.md", exact: true })).toBeVisible()
  await expect(page.locator('[data-message-role="human"]')).toHaveCount(1)
  await expect(page.getByLabel("输入消息")).toBeEnabled()
  await page.screenshot({ path: "output/playwright/native-agent-report.png", fullPage: true })
  expect(errors).toEqual([])
})

test("closing the subscriber does not cancel, explicit stop does", async ({ page }) => {
  await login(page)
  const previousId = await page.evaluate(() => localStorage.getItem("guanxin_active_conversation"))
  await page.getByRole("button", { name: "新建会话", exact: true }).click()
  await expect.poll(() => page.evaluate(() => localStorage.getItem("guanxin_active_conversation"))).not.toBe(previousId)
  await expect(page.getByLabel("输入消息")).toBeEnabled()
  await page.getByLabel("输入消息").fill("流式测试")
  await page.getByLabel("发送消息").click()
  await expect(page.getByLabel("停止生成")).toBeVisible()
  await page.reload()
  await expect(page.locator('[data-message-role="ai"]').filter({ hasText: "测试回复" })).toBeVisible()
  await expect(page.getByLabel("输入消息")).toBeEnabled()
  await page.getByLabel("输入消息").fill("取消测试")
  await page.getByLabel("发送消息").click()
  await expect(page.getByLabel("停止生成")).toBeVisible()
  await page.getByLabel("停止生成").click()
  await expect(page.getByRole("button", { name: "继续任务", exact: true })).toBeVisible()
  await expect(page.getByLabel("输入消息")).toBeEnabled()
  await page.getByRole("button", { name: "继续任务", exact: true }).click()
  await expect(page.getByRole("button", { name: "继续任务", exact: true })).toHaveCount(0)
  await expect(page.getByLabel("输入消息")).toBeEnabled()
  await expect(page.locator('[data-message-role="human"]')).toHaveCount(2)
  await expect(page.locator('[data-message-role="ai"]').filter({ hasText: "测试回复" })).toHaveCount(2)
})
