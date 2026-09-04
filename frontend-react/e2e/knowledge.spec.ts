import { expect, test } from "@playwright/test"

import { authHeaders, login } from "./helpers"

test("knowledge document can be uploaded, inspected, retrieved and deleted", async ({ page }) => {
  await login(page)
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  expect(token).toBeTruthy()
  const headers = authHeaders(token!)
  const filename = `playwright-knowledge-${Date.now()}.txt`
  const uniqueContent = "星河验收标记说明观心知识库端到端链路已经工作。"

  await page.goto("/knowledge")
  await page.locator('input[type="file"]').setInputFiles({
    name: filename,
    mimeType: "text/plain",
    buffer: Buffer.from(uniqueContent, "utf-8"),
  })

  const row = page.getByRole("row").filter({ hasText: filename })
  await expect(row).toBeVisible()
  await expect(row.getByText("就绪", { exact: true })).toBeVisible()

  const documentsResponse = await page.request.get("/api/knowledge/documents", { headers })
  const documents = (await documentsResponse.json()).data as Array<{ doc_id: string; filename: string }>
  const document = documents.find((item) => item.filename === filename)
  expect(document).toBeTruthy()

  try {
    await row.getByRole("button", { name: "查看" }).click()
    await expect(page.getByText("CHUNK 1", { exact: true })).toBeVisible()
    await expect(page.getByText(uniqueContent, { exact: true })).toBeVisible()
    await page.getByRole("button", { name: "关闭详情" }).click()

    await page.getByPlaceholder("输入问题，例如：如何启动观心？").fill("星河验收标记")
    await page.getByRole("button", { name: "开始检索" }).click()
    const retrievalResult = page.locator("article").filter({ hasText: "RESULT" }).filter({ hasText: filename })
    await expect(retrievalResult).toBeVisible()
    await expect(retrievalResult).toContainText(uniqueContent)

    await row.getByRole("button", { name: "删除" }).click()
    await page.getByRole("dialog").getByRole("button", { name: "确认删除" }).click()
    await expect(row).toHaveCount(0)
  } finally {
    if (document) {
      await page.request.delete(`/api/knowledge/documents/${document.doc_id}`, { headers })
    }
  }
})
