"use client"

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts"

type User = { user_id: string; username: string; email: string; role: string; status: string; created_at: string }
type Counts = Record<string, number>
type Statistics = { total: number; roles: Counts; statuses: Counts }
type Filters = { keyword?: string; role?: string }

export type UsersResult = {
  users: User[]
  total: number
  page: number
  page_size: number
  statistics?: Statistics
  filters?: Filters
}

const roles: Record<string, string> = { admin: "管理员", user: "普通用户", viewer: "访客", unknown: "未知角色" }
const statuses: Record<string, string> = { active: "活跃", inactive: "非活跃", unknown: "未知状态" }
const statusColors = ["#059669", "#94a3b8", "#d97706", "#6366f1"]
const barColors = ["#059669", "#3b82f6", "#8b5cf6"]
const userFields: (keyof User)[] = ["user_id", "username", "email", "role", "status", "created_at"]
const columns = ["用户", "邮箱", "角色", "状态", "创建时间"]

const isUser = (value: unknown): value is User =>
  !!value && typeof value === "object"
  && userFields.every((field) => typeof (value as User)[field] === "string")

const isCounts = (value: unknown): value is Counts =>
  !!value && typeof value === "object" && !Array.isArray(value)
  && Object.values(value as Counts).every((count) => Number.isInteger(count) && count >= 0)

const sumCounts = (counts: Counts) => Object.values(counts).reduce((total, count) => total + count, 0)

const isStatistics = (value: unknown, total: number): value is Statistics => {
  if (!value || typeof value !== "object") return false
  const statistics = value as Statistics
  if (!Number.isInteger(statistics.total) || statistics.total !== total) return false
  if (!isCounts(statistics.roles) || !isCounts(statistics.statuses)) return false
  return sumCounts(statistics.roles) === statistics.total && sumCounts(statistics.statuses) === statistics.total
}

const isFilters = (value: unknown): value is Filters => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false
  return Object.values(value as Record<string, unknown>).every((item) => typeof item === "string")
}

/**
 * Parse a skill__query_users tool payload. Fields degrade one by one instead of
 * rejecting the whole result: a broken statistics block falls back to the current
 * page, and malformed user rows are dropped instead of hiding the dashboard.
 */
export function parseUsersResult(text: string): UsersResult | null {
  let payload: unknown
  try {
    payload = JSON.parse(text)
  } catch {
    return null
  }
  if (!payload || typeof payload !== "object") return null
  const result = payload as Record<string, unknown>
  if (result.success === false) return null
  const data = (result.output ?? result) as Record<string, unknown>
  if (!data || typeof data !== "object") return null
  if (!Array.isArray(data.users)) return null
  if (!Number.isInteger(data.total) || (data.total as number) < 0) return null
  const total = data.total as number
  const users = data.users.filter(isUser)
  return {
    users,
    total,
    page: Number.isInteger(data.page) ? (data.page as number) : 1,
    page_size: Number.isInteger(data.page_size) ? (data.page_size as number) : users.length,
    statistics: isStatistics(data.statistics, total) ? data.statistics : undefined,
    filters: isFilters(data.filters) ? data.filters : undefined,
  }
}

function countBy(users: User[], key: "role" | "status"): Counts {
  return users.reduce<Counts>((result, user) => {
    const value = user[key] || "unknown"
    result[value] = (result[value] || 0) + 1
    return result
  }, {})
}

// The model marks a reply that only repeats the dashboard. The marker is the
// contract between prompt and UI, so the rule does not depend on wording.
const markerAtStart = /^\s*\[看板\]\s*/
const markerAnywhere = /\[看板\]/g

/** Every number the dashboard already shows, used to cross-check the marked reply. */
export function dashboardNumbers(data: UsersResult): number[] {
  const numbers = new Set<number>([data.total])
  const roleCounts = data.statistics?.roles ?? countBy(data.users, "role")
  const statusCounts = data.statistics?.statuses ?? countBy(data.users, "status")
  for (const count of Object.values(roleCounts)) numbers.add(count)
  for (const count of Object.values(statusCounts)) numbers.add(count)
  return [...numbers]
}

export function stripDashboardMarker(text: string): string {
  // Strip wherever the model put it, so the contract never leaks into the UI.
  return text.replace(markerAnywhere, "").trim()
}

/**
 * A marked reply is dropped only when every number it mentions is already on the
 * dashboard. A reply that reports a different count stays visible as a mismatch
 * signal, because the dashboard and the model then disagree.
 */
export function isDashboardRestatement(text: string, knownNumbers: number[]): boolean {
  if (!markerAtStart.test(text)) return false
  const mentioned = (text.match(/\d+/g) ?? []).map(Number)
  return mentioned.every((value) => knownNumbers.includes(value))
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return <div className="rounded-xl bg-muted/50 p-3">
    <p className="text-xs text-muted-foreground">{label}</p>
    <p className="mt-2 text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
  </div>
}

function RoleBars({ counts, total }: { counts: Counts; total: number }) {
  return <div className="mt-6 space-y-5">
    {Object.entries(counts).map(([key, value], index) => {
      const label = roles[key] || key
      const share = total ? (value / total) * 100 : 0
      const percent = Math.round(share)
      return <div key={key}>
        <div className="mb-2 flex justify-between gap-2 text-xs">
          <span>{label}</span>
          <span className="tabular-nums text-muted-foreground">{value} 人 · {percent}%</span>
        </div>
        <div
          role="img"
          aria-label={`${label} ${value} 人，占 ${percent}%`}
          className="h-2.5 overflow-hidden rounded-full bg-muted"
        >
          <div
            className="h-full rounded-full"
            style={{ width: `${share}%`, backgroundColor: barColors[index % barColors.length] }}
          />
        </div>
      </div>
    })}
  </div>
}

function StatusChart({ counts, total, rate }: { counts: Counts; total: number; rate: string }) {
  const data = Object.entries(counts).map(([key, value]) => ({
    name: statuses[key] || key,
    value,
    color: key === "active" ? statusColors[0] : key === "inactive" ? statusColors[1] : statusColors[2],
  }))
  return <div className="rounded-xl border p-4">
    <h4 className="text-sm font-medium">活跃状态</h4>
    <div
      className="relative mx-auto h-44 w-full max-w-[240px]"
      role="img"
      aria-label={data.map((item) => `${item.name} ${item.value} 人`).join("，")}
    >
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            innerRadius={54}
            outerRadius={72}
            stroke="none"
            paddingAngle={data.length > 1 ? 3 : 0}
            isAnimationActive={false}
          >
            {data.map((item) => <Cell key={item.name} fill={item.color} />)}
          </Pie>
          <Tooltip
            formatter={(value: number) => [`${value} 人`, "人数"]}
            contentStyle={{ background: "hsl(var(--card))", color: "hsl(var(--foreground))", borderRadius: 10 }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold tabular-nums">{rate}</span>
        <span className="mt-1 text-xs text-muted-foreground">活跃率</span>
      </div>
    </div>
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-2">
      {data.map((item) => <span key={item.name} className="flex items-center gap-1.5 text-xs">
        <span className="h-2 w-2 rounded-full" style={{ background: item.color }} />
        {item.name} {item.value} 人 · {Math.round((item.value / total) * 100)}%
      </span>)}
    </div>
  </div>
}

function UserTable({ users, page }: { users: User[]; page: number }) {
  return <details className="rounded-xl border">
    <summary className="cursor-pointer px-4 py-3 text-sm font-medium">
      用户明细 <span className="ml-2 font-normal text-muted-foreground">本页 {users.length} 人 · 第 {page} 页</span>
    </summary>
    <div className="overflow-x-auto border-t">
      <table className="w-full whitespace-nowrap text-left text-xs">
        <thead className="bg-muted/50 text-muted-foreground">
          <tr>{columns.map((label) => <th key={label} className="px-4 py-3 font-medium">{label}</th>)}</tr>
        </thead>
        <tbody>
          {users.map((user) => <tr key={user.user_id} className="border-t">
            <td className="px-4 py-3">
              <div className="font-medium">{user.username}</div>
              <div className="mt-1 text-muted-foreground">{user.user_id}</div>
            </td>
            <td className="px-4 py-3">{user.email}</td>
            <td className="px-4 py-3">
              <span className="rounded-md bg-primary/10 px-2 py-1 text-primary">{roles[user.role] || user.role}</span>
            </td>
            <td className="px-4 py-3">
              <span className={`rounded-full px-2 py-1 ${user.status === "active"
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                : "bg-muted text-muted-foreground"}`}>
                {statuses[user.status] || user.status}
              </span>
            </td>
            <td className="px-4 py-3 text-muted-foreground">{user.created_at.slice(0, 10)}</td>
          </tr>)}
        </tbody>
      </table>
      {!users.length && <p className="p-4 text-sm text-muted-foreground">当前页没有用户。</p>}
    </div>
  </details>
}

export function UsersDashboard({ data }: { data: UsersResult }) {
  const total = data.statistics?.total ?? data.users.length
  const roleCounts = data.statistics?.roles ?? countBy(data.users, "role")
  const statusCounts = data.statistics?.statuses ?? countBy(data.users, "status")
  const active = statusCounts.active || 0
  const rate = total ? `${Math.round((active / total) * 100)}%` : "—"
  const pageOnly = !data.statistics && data.total > data.users.length
  const scope = pageOnly ? "图表与指标仅统计当前页" : "统计范围：全部匹配用户"
  const keyword = data.filters?.keyword ? ` · 关键词：${data.filters.keyword}` : ""
  const roleFilter = data.filters?.role ? ` · 角色：${roles[data.filters.role] || data.filters.role}` : ""
  const tiles = [
    { label: pageOnly ? "本页用户" : "用户总数", value: total },
    { label: "活跃用户", value: active },
    { label: "非活跃用户", value: statusCounts.inactive || 0 },
    { label: "活跃率", value: rate },
  ]
  return <section aria-label="用户统计看板" className="min-w-0 overflow-hidden rounded-2xl border bg-card shadow-sm">
    <header className="border-b px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">用户统计</h3>
        <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs text-primary">查询结果 · {data.total} 人</span>
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">{scope}{keyword}{roleFilter}</p>
    </header>
    <div className="space-y-5 p-4 sm:p-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tiles.map((item) => <StatTile key={item.label} label={item.label} value={item.value} />)}
      </div>
      {total === 0
        ? <div className="rounded-xl border border-dashed py-10 text-center text-sm text-muted-foreground">
          未找到匹配用户，请调整关键词或角色筛选。
        </div>
        : <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border p-4">
            <h4 className="text-sm font-medium">角色分布</h4>
            <RoleBars counts={roleCounts} total={total} />
          </div>
          <StatusChart counts={statusCounts} total={total} rate={rate} />
        </div>}
      <UserTable users={data.users} page={data.page || 1} />
    </div>
  </section>
}
