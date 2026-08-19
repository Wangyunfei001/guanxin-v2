import Assistant from "@/app/assistant";

/**
 * AG-UI 协议集成测试页 — 使用 assistant-ui Thread + AG-UI Runtime。
 *
 * 路由: /assistant
 * 访问前需确保 AG-UI 后端 agent 已启动并配置 NEXT_PUBLIC_AG_UI_AGENT_URL。
 */
export default function AssistantPage() {
  return <Assistant />;
}