import { expect, test } from "@playwright/test"

import { authHeaders, login, tokenFor } from "./helpers"

test("upload above the size ceiling is rejected without persisting anything", async ({ page }) => {
  await login(page)
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  expect(token).toBeTruthy()

  // The e2e backend runs with a 1 MB ceiling; push 2 MB through it.
  const response = await page.request.post("/api/knowledge/documents/upload", {
    headers: authHeaders(token as string),
    multipart: {
      file: {
        name: "oversized.txt",
        mimeType: "text/plain",
        buffer: Buffer.alloc(2 * 1024 * 1024, "a"),
      },
    },
  })
  expect(response.status()).toBe(413)
  expect((await response.json()).detail).toContain("上限")

  // Nothing may be left behind in the knowledge base.
  const documents = await page.request.get("/api/knowledge/documents", {
    headers: authHeaders(token as string),
  })
  const names = (await documents.json()).data.map((item: { filename: string }) => item.filename)
  expect(names).not.toContain("oversized.txt")
})

test("MCP servers are isolated per tenant", async ({ page }) => {
  await login(page)
  const tenantA = authHeaders(
    (await page.evaluate(() => localStorage.getItem("access_token"))) as string,
  )
  const tenantB = authHeaders(await tokenFor(page.request, "demo", "demo123"))

  const name = `e2e-isolated-${Date.now()}`
  const created = await page.request.post("/api/mcp/servers", {
    headers: tenantA,
    data: { name, command: "python", args: [], description: "租户 A 私有" },
  })
  expect(created.ok()).toBeTruthy()

  const listA = await page.request.get("/api/mcp/servers", { headers: tenantA })
  const namesA = (await listA.json()).data.map((item: { name: string }) => item.name)
  expect(namesA).toContain(name)

  // The other tenant must not see it at all.
  const listB = await page.request.get("/api/mcp/servers", { headers: tenantB })
  const namesB = (await listB.json()).data.map((item: { name: string }) => item.name)
  expect(namesB).not.toContain(name)

  // And it must not be able to delete it.
  const deleted = await page.request.delete(`/api/mcp/servers/${name}`, { headers: tenantB })
  expect((await deleted.json()).code).toBe(4041)

  const stillThere = await page.request.get("/api/mcp/servers", { headers: tenantA })
  const namesAfter = (await stillThere.json()).data.map((item: { name: string }) => item.name)
  expect(namesAfter).toContain(name)
})

test("MCP server environment values never reach the client", async ({ page }) => {
  await login(page)
  const tenantA = authHeaders(
    (await page.evaluate(() => localStorage.getItem("access_token"))) as string,
  )
  const tenantB = authHeaders(await tokenFor(page.request, "demo", "demo123"))

  const secret = "sk-e2e-secret-value"
  const name = `e2e-secret-${Date.now()}`
  await page.request.post("/api/mcp/servers", {
    headers: tenantA,
    data: { name, command: "python", args: [], env: { OPENAI_API_KEY: secret } },
  })

  for (const headers of [tenantA, tenantB]) {
    const response = await page.request.get("/api/mcp/servers", { headers })
    expect(await response.text()).not.toContain(secret)
  }
})
