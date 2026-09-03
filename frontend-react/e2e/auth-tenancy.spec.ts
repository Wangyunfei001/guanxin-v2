import { expect, test } from "@playwright/test"

import { authHeaders, login, tokenFor } from "./helpers"

test("navigation, role permissions and tenant isolation are enforced", async ({ page }) => {
  await login(page)
  await page.getByRole("button", { name: "展开导航" }).click()

  for (const name of ["Assistant", "知识库", "Skills", "MCP 服务", "Agent 配置", "A2UI 实验室"]) {
    await expect(page.getByRole("navigation").getByRole("link", { name })).toBeVisible()
  }

  const adminToken = await page.evaluate(() => localStorage.getItem("access_token"))
  expect(adminToken).toBeTruthy()
  const adminHeaders = authHeaders(adminToken!)
  const marker = `tenant-a-only-${Date.now()}.txt`
  const upload = await page.request.post("/api/knowledge/documents/upload", {
    headers: adminHeaders,
    multipart: {
      title: marker,
      file: {
        name: marker,
        mimeType: "text/plain",
        buffer: Buffer.from("这份内容只属于 tenant-a。", "utf-8"),
      },
    },
  })
  const uploaded = (await upload.json()).data

  try {
    const demoToken = await tokenFor(page.request, "demo", "demo123")
    const demoHeaders = authHeaders(demoToken)
    const documents = await page.request.get("/api/knowledge/documents", { headers: demoHeaders })
    expect((await documents.json()).data.map((item: { doc_id: string }) => item.doc_id)).not.toContain(
      uploaded.doc_id,
    )
    const hiddenDocument = await page.request.get(`/api/knowledge/documents/${uploaded.doc_id}`, {
      headers: demoHeaders,
    })
    expect((await hiddenDocument.json()).code).toBe(4041)

    const userToken = await tokenFor(page.request, "user", "user123")
    const userHeaders = authHeaders(userToken)
    const currentConfig = (await (await page.request.get("/api/agent/config", {
      headers: userHeaders,
    })).json()).data
    const forbidden = await page.request.put("/api/agent/config", {
      headers: userHeaders,
      data: {
        model: currentConfig.model,
        temperature: currentConfig.temperature,
        max_tokens: currentConfig.max_tokens,
        system_prompt: currentConfig.system_prompt,
        enabled_tools: currentConfig.enabled_tools,
        enabled_skills: currentConfig.enabled_skills,
        mcp_servers: currentConfig.mcp_servers,
      },
    })
    expect(forbidden.status()).toBe(403)
  } finally {
    await page.request.delete(`/api/knowledge/documents/${uploaded.doc_id}`, {
      headers: adminHeaders,
    })
  }
})
