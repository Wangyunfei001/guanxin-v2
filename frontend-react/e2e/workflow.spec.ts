import { expect, test } from "@playwright/test"

import { login } from "./helpers"

test("persistent workflow collects input, executes approval and survives refresh", async ({ page }) => {
  await login(page)

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

  let conversationId: string | undefined
  let createdUserId: string | undefined
  try {
    const conversationResponse = await page.request.post("/api/agent/conversations", {
      headers,
      data: { title: "Playwright 工作流" },
    })
    expect(conversationResponse.ok()).toBeTruthy()
    const conversation = (await conversationResponse.json()).data
    conversationId = conversation.conversation_id
    expect(conversationId).toBeTruthy()
    await page.evaluate((conversationId) => {
      localStorage.setItem("guanxin_active_conversation", conversationId)
    }, conversation.conversation_id)
    await page.reload()
    await expect(page.getByRole("button", { name: "Playwright 工作流" }).first()).toBeVisible()

    const composer = page.getByLabel("输入消息")
    const sendButton = page.getByRole("button", { name: "发送消息" })
    const attachmentButton = page.getByRole("button", { name: "添加文本附件" })
    const researchMode = page.getByRole("combobox", { name: "研究模式" })
    const composerShell = page.locator('[data-slot="agent-composer"]')

    await expect(sendButton).toBeDisabled()
    await expect(attachmentButton).toBeEnabled()
    await expect(researchMode).toBeEnabled()
    await expect(composerShell).toHaveCSS("border-radius", "18px")

    const initialHeight = await composer.evaluate((element) => element.getBoundingClientRect().height)
    await composer.fill("第一行\n第二行\n第三行")
    const multilineHeight = await composer.evaluate((element) => element.getBoundingClientRect().height)
    expect(multilineHeight).toBeGreaterThan(initialHeight)
    await composer.fill("第一行")
    await composer.press("Shift+Enter")
    await expect(composer).toHaveValue("第一行\n")

    await composer.fill("创建一个用户")
    await expect(sendButton).toBeEnabled()
    const chatResponsePromise = page.waitForResponse((response) =>
      response.url().includes("/commands"),
    )
    await sendButton.click()
    expect((await chatResponsePromise).ok()).toBeTruthy()

    const workflowTrack = page.getByText("执行轨迹", { exact: true })
    await expect(workflowTrack).toHaveCount(1)
    await expect(page.getByText("1 tool call", { exact: true })).toHaveCount(0)
    await expect(page.getByText("补充参数：创建用户")).toBeVisible()
    await expect(composer).toBeDisabled()
    await expect(sendButton).toBeDisabled()
    await expect(attachmentButton).toBeDisabled()
    await expect(researchMode).toBeDisabled()
    const workflowUsername = `playwright-user-${Date.now()}`
    await page.getByPlaceholder("用户名（登录名）").fill(workflowUsername)
    await page.getByPlaceholder("邮箱地址").fill(`${workflowUsername}@example.com`)
    await page.getByRole("button", { name: "提交并继续" }).click()

    await expect(workflowTrack).toHaveCount(1)
    await expect(page.getByText("1 tool call", { exact: true })).toHaveCount(0)
    await expect(page.getByText("确认执行：创建用户")).toBeVisible()
    await expect(page.getByText("响应已提交，工作流正在继续。")).toHaveCount(0)
    await page.getByRole("button", { name: "批准执行" }).click()
    await expect(workflowTrack).toHaveCount(1)
    await expect(page.getByText("已完成", { exact: true }).first()).toBeVisible()
    await expect(page.locator('[data-slot="workflow-control"]')).toHaveCount(0)
    await expect(page.getByText("响应已提交，工作流正在继续。")).toHaveCount(0)

    const queryResponse = await page.request.post("/api/skills/execute", {
      headers,
      data: {
        skill_name: "query_users",
        params: { keyword: workflowUsername },
      },
    })
    const users = (await queryResponse.json()).data.output.users
    expect(users).toHaveLength(1)
    createdUserId = users[0].user_id

    await page.reload()
    await expect(workflowTrack).toHaveCount(1)
    await expect(page.getByText("创建一个用户", { exact: true }).first()).toBeVisible()
    await expect(page.getByText("已完成", { exact: true }).first()).toBeVisible()
  } finally {
    if (createdUserId) {
      await page.request.post("/api/skills/execute", {
        headers,
        data: { skill_name: "delete_user", params: { user_id: createdUserId } },
      })
    }
    if (conversationId) {
      await page.request.delete(`/api/agent/conversations/${conversationId}`, { headers })
    }
    const restoreResponse = await page.request.put("/api/agent/config", { headers, data: payload })
    expect(restoreResponse.ok()).toBeTruthy()
  }
})
