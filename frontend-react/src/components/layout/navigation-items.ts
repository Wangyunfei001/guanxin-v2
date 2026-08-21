import {
  Books,
  ChatCircleDots,
  GridFour,
  Lightning,
  PlugsConnected,
  Robot,
} from "@phosphor-icons/react"

export const navigationGroups = [
  {
    label: "工作台",
    items: [{ href: "/assistant", label: "Assistant", icon: ChatCircleDots }],
  },
  {
    label: "能力中心",
    items: [
      { href: "/knowledge", label: "知识库", icon: Books },
      { href: "/skills", label: "Skills", icon: Lightning },
      { href: "/mcp", label: "MCP 服务", icon: PlugsConnected },
    ],
  },
  {
    label: "系统配置",
    items: [
      { href: "/agent", label: "Agent 配置", icon: Robot },
      { href: "/a2ui", label: "A2UI 实验室", icon: GridFour },
    ],
  },
] as const

export const pageTitles: Record<string, string> = Object.fromEntries(
  navigationGroups.flatMap((group) => group.items.map((item) => [item.href, item.label])),
)
