import { expect, test } from "@playwright/test"

import { login } from "./helpers"

test("data analysis skill result and A2UI chart render", async ({ page }) => {
  await login(page)
  await page.goto("/skills")

  const skill = page.locator("article").filter({ hasText: "data_analysis" })
  await expect(skill).toBeVisible()
  await skill.getByRole("button", { name: "试运行" }).click()

  const runner = page.getByRole("dialog").filter({ hasText: "SKILL RUNNER" })
  await runner.locator("input").nth(0).fill("[1, 2, 3, 4, 5]")
  await runner.locator("input").nth(1).fill("full")
  await runner.getByRole("button", { name: "执行 Skill" }).click()

  const result = page.getByRole("dialog").filter({ hasText: "执行结果" })
  await expect(result).toContainText('"mean": 3')
  await expect(result).toContainText('"chart_data"')
  await result.getByRole("button", { name: "关闭" }).click()

  await page.goto("/a2ui")
  await page.getByRole("button", { name: /data_analysis/ }).click()
  await expect(page.getByText("数据分析", { exact: true }).first()).toBeVisible()
  await expect(page.locator(".recharts-responsive-container")).toBeVisible()
  await expect(page.getByText("Schema JSON", { exact: true })).toBeVisible()
})
