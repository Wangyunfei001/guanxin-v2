import { describe, expect, it } from "vitest"

import {
  dashboardNumbers,
  isDashboardRestatement,
  parseUsersResult,
  stripDashboardMarker,
} from "./users-dashboard-data"

const user = (index: number) => ({
  user_id: `usr_${index}`,
  username: `用户${index}`,
  email: `user${index}@example.com`,
  role: index === 0 ? "admin" : "user",
  status: index === 2 ? "inactive" : "active",
  created_at: "2026-01-15",
})

const payload = (overrides: Record<string, unknown> = {}) =>
  JSON.stringify({
    success: true,
    output: {
      users: [user(0), user(1), user(2)],
      total: 3,
      page: 1,
      page_size: 10,
      statistics: {
        total: 3,
        roles: { admin: 1, user: 2 },
        statuses: { active: 2, inactive: 1 },
      },
      filters: { keyword: "", role: "" },
      ...overrides,
    },
  })

describe("parseUsersResult", () => {
  it("解析完整的工具输出", () => {
    const result = parseUsersResult(payload())
    expect(result).not.toBeNull()
    expect(result?.users).toHaveLength(3)
    expect(result?.total).toBe(3)
    expect(result?.statistics?.roles).toEqual({ admin: 1, user: 2 })
    expect(result?.filters).toEqual({ keyword: "", role: "" })
  })

  it("非法 JSON 返回 null", () => {
    expect(parseUsersResult("not json")).toBeNull()
    expect(parseUsersResult("[]")).toBeNull()
  })

  it("工具标记失败时返回 null", () => {
    expect(
      parseUsersResult(JSON.stringify({ success: false, error: "角色筛选不支持 member" })),
    ).toBeNull()
  })

  it("缺少 users 数组时返回 null", () => {
    expect(parseUsersResult(JSON.stringify({ success: true, output: { total: 1 } }))).toBeNull()
  })

  it("统计块与总数不一致时只丢掉统计块，看板退回本页口径", () => {
    const result = parseUsersResult(
      payload({
        statistics: {
          total: 99,
          roles: { admin: 1 },
          statuses: { active: 3 },
        },
      }),
    )
    expect(result).not.toBeNull()
    expect(result?.statistics).toBeUndefined()
    expect(result?.users).toHaveLength(3)
  })

  it("单条用户记录字段不全时只丢掉该条记录", () => {
    const broken = payload().replace('"email":"user1@example.com"', '"email":42')
    const result = parseUsersResult(broken)
    expect(result?.users).toHaveLength(2)
    expect(result?.total).toBe(3)
  })

  it("filters 形状不合法时被丢弃", () => {
    const result = parseUsersResult(payload({ filters: { keyword: 42 } }))
    expect(result?.filters).toBeUndefined()
  })
})

describe("dashboardNumbers", () => {
  it("收集总数、角色数与状态数", () => {
    const result = parseUsersResult(payload())
    const numbers = dashboardNumbers(result!)
    expect(numbers).toContain(3)
    expect(numbers).toContain(1)
    expect(numbers).toContain(2)
  })

  it("没有统计块时用本页数据计算", () => {
    const result = parseUsersResult(
      payload({
        statistics: { total: 99, roles: {}, statuses: {} },
      }),
    )
    const numbers = dashboardNumbers(result!)
    expect(numbers).toContain(3)
    expect(numbers).toContain(2)
  })
})

describe("stripDashboardMarker", () => {
  it("剥离标记并去掉首尾空白", () => {
    expect(stripDashboardMarker("[看板] 以下是统计")).toBe("以下是统计")
  })

  it("标记出现在句中也会被剥离", () => {
    expect(stripDashboardMarker("共 [看板] 7 个用户")).toBe("共 7 个用户")
  })

  it("没有标记时原样返回", () => {
    expect(stripDashboardMarker("普通回答")).toBe("普通回答")
  })
})

describe("isDashboardRestatement", () => {
  const known = [7, 6, 1]

  it("带标记且数字都与看板一致时判定为复述", () => {
    expect(isDashboardRestatement("[看板] 共 7 个用户，其中 6 人活跃。", known)).toBe(true)
  })

  it("数字与看板不一致时保留正文（不一致是错误信号）", () => {
    expect(isDashboardRestatement("[看板] 共 9 个用户。", known)).toBe(false)
  })

  it("没有标记时不算复述", () => {
    expect(isDashboardRestatement("共 7 个用户。", known)).toBe(false)
  })

  it("标记不在开头时不算复述", () => {
    expect(isDashboardRestatement("共 7 个用户。[看板]", known)).toBe(false)
  })

  it("没有数字的标记回复算复述", () => {
    expect(isDashboardRestatement("[看板] 统计如上。", known)).toBe(true)
  })
})
