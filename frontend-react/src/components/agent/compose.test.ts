import { describe, expect, it } from "vitest"

import { composeMessage, exceedsInputLimit, MAX_INPUT_CHARS } from "./compose"

describe("composeMessage", () => {
  it("没有附件时原样返回正文", () => {
    expect(composeMessage("创建一个用户", null)).toBe("创建一个用户")
  })

  it("带附件时把附件内容拼在正文后面", () => {
    const content = composeMessage("总结这份文档", {
      name: "notes.txt",
      content: "第一行\n第二行",
    })
    expect(content).toContain("总结这份文档")
    expect(content).toContain("notes.txt")
    expect(content).toContain("第一行\n第二行")
  })
})

describe("exceedsInputLimit", () => {
  it("恰好等于上限不算超限", () => {
    expect(exceedsInputLimit("a".repeat(MAX_INPUT_CHARS))).toBe(false)
  })

  it("超出上限时返回 true", () => {
    expect(exceedsInputLimit("a".repeat(MAX_INPUT_CHARS + 1))).toBe(true)
  })

  it("支持自定义上限", () => {
    expect(exceedsInputLimit("abcde", 4)).toBe(true)
    expect(exceedsInputLimit("abcd", 4)).toBe(false)
  })
})
