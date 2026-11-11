import { expect, type APIRequestContext, type Page } from "@playwright/test"

export async function login(page: Page, username = "admin", password = "admin123") {
  await page.goto("/login")
  await page.getByLabel("用户名").fill(username)
  await page.getByLabel("密码").fill(password)
  await page.getByRole("button", { name: "进入工作空间", exact: true }).click()
  await expect(page).toHaveURL(/\/assistant$/)
}

export async function tokenFor(
  request: APIRequestContext,
  username: string,
  password: string,
) {
  const response = await request.post("/api/auth/login", {
    data: { username, password },
  })
  expect(response.ok()).toBeTruthy()
  const payload = await response.json()
  expect(payload.code).toBe(0)
  return payload.data.access_token as string
}

export function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` }
}

/**
 * 等待编辑器稳定。
 *
 * 切换或新建会话会重建线程组件（AgentThread 以会话 id 为 key）。重建完成
 * 之前输入会落到已被卸载的旧节点上，文字会凭空消失——真实用户也会遇到
 * 「新建会话后立刻打字，什么都没打进去」。
 */
export async function waitForComposerStable(page: Page) {
  await expect
    .poll(
      async () => {
        const before = await page
          .locator('[data-slot="agent-composer"]')
          .getAttribute("data-mount-id")
        await page.waitForTimeout(150)
        const after = await page
          .locator('[data-slot="agent-composer"]')
          .getAttribute("data-mount-id")
        return before === after ? after : null
      },
      { timeout: 15_000 },
    )
    .not.toBeNull()
}
