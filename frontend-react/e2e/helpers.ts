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
