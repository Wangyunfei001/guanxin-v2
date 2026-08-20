import { expect, test } from "@playwright/test"

test("persistent workflow shows plan, collects input and survives refresh", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel("用户名").fill("admin")
  await page.getByLabel("密码").fill("admin123")
  await page.getByRole("button", { name: "登录", exact: true }).click()
  await expect(page).toHaveURL(/\/assistant$/)

  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  expect(token).toBeTruthy()
  const headers = { Authorization: `Bearer ${token}` }
  const configResponse = await page.request.get("/api/agent/config", { headers })
  const config = (await configResponse.json()).data
  const payload = {
    model: config.model,
    temperature: config.temperature,
    max_tokens: config.max_tokens,
    system_prompt: config.system_prompt,
    enabled_tools: config.enabled_tools,
    enabled_skills: config.enabled_skills,
    mcp_servers: config.mcp_servers,
  }

  const updateResponse = await page.request.put("/api/agent/config", {
    headers,
    data: {
      ...payload,
      enabled_skills: Array.from(new Set([...payload.enabled_skills, "create_user"])),
    },
  })
  expect(updateResponse.ok()).toBeTruthy()

  try {
    const conversationResponse = await page.request.post("/api/agent/conversations", {
      headers,
      data: { title: "Playwright 工作流" },
    })
    expect(conversationResponse.ok()).toBeTruthy()
    const conversation = (await conversationResponse.json()).data
    await page.evaluate((conversationId) => {
      localStorage.setItem("guanxin_active_conversation", conversationId)
    }, conversation.id)
    await page.reload()
    await expect(page.getByRole("button", { name: "Playwright 工作流" })).toBeVisible()

    const composer = page.getByLabel("Message input")
    await composer.fill("创建一个用户")
    const chatResponsePromise = page.waitForResponse((response) =>
      response.url().includes("/api/agent/chat/aisdk"),
    )
    await page.getByRole("button", { name: "Send message" }).click()
    expect((await chatResponsePromise).status()).toBe(200)

    await expect(page.getByText("补充参数：创建用户")).toBeVisible()
    await page.getByPlaceholder("用户名（登录名）").fill("playwright-user")
    await page.getByPlaceholder("邮箱地址").fill("playwright@example.com")
    await page.getByRole("button", { name: "提交并继续" }).click()

    await expect(page.getByText("确认执行：创建用户")).toBeVisible()
    await page.getByRole("button", { name: "取消流程" }).last().click()
    await expect(page.getByText("已取消", { exact: true }).first()).toBeVisible()

    await page.reload()
    await expect(page.getByText("创建一个用户", { exact: true }).first()).toBeVisible()
    await expect(page.getByText("已取消", { exact: true }).first()).toBeVisible()
  } finally {
    const restoreResponse = await page.request.put("/api/agent/config", { headers, data: payload })
    expect(restoreResponse.ok()).toBeTruthy()
  }
})
