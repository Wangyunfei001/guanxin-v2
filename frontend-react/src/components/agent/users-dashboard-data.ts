/**
 * 用户统计看板的纯数据逻辑。
 *
 * 与 React 组件分开，既让解析规则可以脱离浏览器直接测试，也让组件只负责
 * 呈现。解析按**字段降级**——统计块坏了退回本页口径，坏掉的用户行被丢弃
 * 而不是让整块看板消失。
 */

export type User = {
  user_id: string
  username: string
  email: string
  role: string
  status: string
  created_at: string
}

export type Counts = Record<string, number>

export type Statistics = { total: number; roles: Counts; statuses: Counts }

export type Filters = { keyword?: string; role?: string }

export type UsersResult = {
  users: User[]
  total: number
  page: number
  page_size: number
  statistics?: Statistics
  filters?: Filters
}

const userFields: (keyof User)[] = [
  "user_id",
  "username",
  "email",
  "role",
  "status",
  "created_at",
]

const isUser = (value: unknown): value is User =>
  !!value &&
  typeof value === "object" &&
  userFields.every((field) => typeof (value as User)[field] === "string")

const isCounts = (value: unknown): value is Counts =>
  !!value &&
  typeof value === "object" &&
  !Array.isArray(value) &&
  Object.values(value as Counts).every(
    (count) => Number.isInteger(count) && count >= 0,
  )

const sumCounts = (counts: Counts) =>
  Object.values(counts).reduce((total, count) => total + count, 0)

const isStatistics = (value: unknown, total: number): value is Statistics => {
  if (!value || typeof value !== "object") return false
  const statistics = value as Statistics
  if (!Number.isInteger(statistics.total) || statistics.total !== total) return false
  if (!isCounts(statistics.roles) || !isCounts(statistics.statuses)) return false
  return (
    sumCounts(statistics.roles) === statistics.total &&
    sumCounts(statistics.statuses) === statistics.total
  )
}

const isFilters = (value: unknown): value is Filters => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false
  return Object.values(value as Record<string, unknown>).every(
    (item) => typeof item === "string",
  )
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
    page_size: Number.isInteger(data.page_size)
      ? (data.page_size as number)
      : users.length,
    statistics: isStatistics(data.statistics, total)
      ? data.statistics
      : undefined,
    filters: isFilters(data.filters) ? data.filters : undefined,
  }
}

export function countBy(
  users: User[],
  key: "role" | "status",
): Counts {
  return users.reduce<Counts>((result, user) => {
    const value = user[key] || "unknown"
    result[value] = (result[value] || 0) + 1
    return result
  }, {})
}

// The model marks a reply that only repeats the dashboard. The marker is the
// contract between prompt and UI, so the rule does not depend on wording.
const markerAtStart = /^\s*\[看板\]\s*/
const markerAnywhere = /\[看板\][ \t]*/g

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
export function isDashboardRestatement(
  text: string,
  knownNumbers: number[],
): boolean {
  if (!markerAtStart.test(text)) return false
  const mentioned = (text.match(/\d+/g) ?? []).map(Number)
  return mentioned.every((value) => knownNumbers.includes(value))
}
