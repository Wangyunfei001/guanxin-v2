# 架构切换方案：AG-UI → AI SDK + assistant-ui + AI Elements

## 目标架构

```
用户发消息
    ↓
assistant-ui Thread (聊天壳：消息列表、Composer、BranchPicker、ActionBar)
    ↓
@assistant-ui/react-ai-sdk (useChatRuntime)
    ↓
AI SDK 协议 (streamText → createUIMessageStreamResponse)
    ↓
后端 execute_agent() (保持不变：intent → mode → ReAct executor)
    ↓
Agent 自主选择工具 → 工具结果映射到 AI Elements 组件
    ├─ kb_retrieval  → <Sources> / <ListCard>
    ├─ show_plan     → <Plan>
    ├─ show_code     → <CodeBlock>
    ├─ confirm       → <Confirmation>
    ├─ chart_data    → <ChartCard> (保留 recharts)
    └─ generic info  → <Tool> fallback
```

---

## 阶段 1：后端新增 AI SDK 端点

### 1.1 新增依赖

```bash
# backend/requirements.txt 新增
ai == 推荐版本
```

Python AI SDK 包不需要安装——只需要按 AI SDK 的 wire format 输出 SSE。格式文档见 [AI SDK Stream Protocol](https://ai-sdk.dev/docs/ai-sdk-core/stream-protocol)。

### 1.2 新增端点 `POST /api/agent/chat/aisdk`

**文件**: `backend/app/api/aisdk.py` (新建)

与 AG-UI 端点平级，复用同一个 `execute_agent()`。区别是输出格式：

| 内部 SSE Event | AG-UI 输出 | AI SDK 输出 (UIMessage stream) |
|---|---|---|
| `token` | `TEXT_MESSAGE_START` + `TEXT_MESSAGE_CONTENT` | `0:"text-delta"\n` |
| `tool_call` | `TOOL_CALL_START` + `TOOL_CALL_ARGS` | `9:{"toolCallId":"...","toolName":"...","args":{...}}\n` |
| `tool_result` | `TOOL_CALL_END` | `a:{"toolCallId":"...","result":"..."}\n` |
| `confirm_required` | `CUSTOM confirm_form` | `9:{"toolCallId":"confirm","toolName":"confirm_action","args":{...}}\n` (作为 tool call 发出) |
| `a2ui` | `CUSTOM a2ui` | 合并到 tool_result 的 result 字段中 |
| `done` | `TEXT_MESSAGE_END` + `RUN_FINISHED` | `d:{"finishReason":"stop"}\n` |
| `error` | `RUN_ERROR` | `3:"error message"\n` 或 `d:{"finishReason":"error"}\n` |

**关键变化**：
- `confirm_required` 不再用 custom event，而是作为 `confirm_action` tool call 发出
- `a2ui` schema 不再单独发送，而是嵌入到 tool_result 的 result JSON 中
- 不再需要 `RUN_STARTED` / `RUN_FINISHED`（AI SDK 协议没有这些）

### 1.3 AG-UI 端点保留

`backend/app/api/agui.py` **不删除**，作为过渡保留。前端迁移完成后可移除。

---

## 阶段 2：前端依赖切换

### 2.1 删除的包

```bash
npm uninstall @ag-ui/client @assistant-ui/react-ag-ui
```

### 2.2 新增的包

```bash
npm install ai @ai-sdk/react @assistant-ui/react-ai-sdk
```

### 2.3 package.json 变化

```diff
- "@ag-ui/client": "^0.0.57"
- "@assistant-ui/react-ag-ui": "^0.0.44"
+ "ai": "^4.x"
+ "@ai-sdk/react": "^1.x"
+ "@assistant-ui/react-ai-sdk": "^0.14.x"
```

---

## 阶段 3：安装 AI Elements 组件

### 3.1 基础聊天组件（替代现有手写版）

```bash
npx ai-elements@latest add message
npx ai-elements@latest add conversation
npx ai-elements@latest add prompt-input
npx ai-elements@latest add tool
npx ai-elements@latest add reasoning
npx ai-elements@latest add code-block
npx ai-elements@latest add sources
npx ai-elements@latest add confirmation
```

这些会**覆盖** `src/components/ai-elements/` 下手写的同名文件。手写文件先备份或删除。

### 3.2 Agent 驱动组件（新安装）

```bash
npx ai-elements@latest add plan
npx ai-elements@latest add task
npx ai-elements@latest add file-tree
npx ai-elements@latest add terminal
npx ai-elements@latest add schema-display
```

### 3.3 删除的手写文件

```bash
rm src/components/ai-elements/actions.tsx       # AI Elements 有内置的
rm src/components/ai-elements/response.tsx       # 被 MessageResponse 替代
```

---

## 阶段 4：Runtime Provider 重写

### 4.1 新文件：`src/components/assistant-ui/aisdk-runtime-provider.tsx`

**职责**：替代 `ag-ui-runtime-provider.tsx`

```tsx
// 伪代码结构
"use client";
import { AssistantRuntimeProvider, useAui, Tools, defineToolkit } from "@assistant-ui/react";
import { useChatRuntime } from "@assistant-ui/react-ai-sdk";
import { useChat } from "@ai-sdk/react";

// 1. 定义 Agent 工具 → AI Elements 组件的映射
const agentToolkit = defineToolkit({
  // Agent 调用的工具名 → 前端渲染的组件
  kb_retrieval: { type: "backend", render: KbRetrievalRenderer },
  execute_skill: { type: "backend", render: SkillResultRenderer },
  confirm_action: { type: "backend", render: ConfirmActionRenderer },
  // ... 按需扩展
});

export function AiSdkRuntimeProvider({ children }) {
  const chat = useChat({
    api: "/api/agent/chat/aisdk",
    // 关键：支持多步 tool call（agent 可能连续调用多个工具）
    sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithApprovalResponses,
  });

  const runtime = useChatRuntime({
    chat,
    // adapters: { attachments, history, ... } // 后续按需添加
  });

  const aui = useAui({ tools: Tools({ toolkit: agentToolkit }) });

  return (
    <AssistantRuntimeProvider runtime={runtime} aui={aui}>
      <A2UISchemasProvider>  {/* 替代旧的 ConfirmFormContext */}
        {children}
      </A2UISchemasProvider>
    </AssistantRuntimeProvider>
  );
}
```

### 4.2 删除的文件

```bash
rm src/components/assistant-ui/ag-ui-runtime-provider.tsx
```

---

## 阶段 5：Thread 组件适配

### 5.1 `src/components/assistant-ui/thread.tsx` 改动

当前 `thread.tsx` 已经使用 `@assistant-ui/react` 的 primitives（`ThreadPrimitive`, `MessagePrimitive`, `ComposerPrimitive` 等），这些**不需要改**。assistant-ui 的 primitives 与 runtime 无关——它们通过 `AssistantRuntimeProvider` context 消费 runtime，无论是 AG-UI 还是 AI SDK。

**需要改的部分**：

1. **删除 `ConfirmFormContext` 引用**——不再从 `useConfirmForm()` 读数据
2. **新增工具渲染器注册**——在 `AssistantMessage` 的 `GroupedParts` 中，为 agent 的 tool-call 类型注册 AI Elements 组件渲染器
3. **删除 `A2UISchemasSection`**——A2UI 改为嵌入 tool_result 中，不再单独渲染

### 5.2 `src/app/assistant.tsx` 简化

```diff
- import { AgUiRuntimeProvider, useConfirmForm } from "..."
+ import { AiSdkRuntimeProvider } from "..."

export default function Assistant() {
  return (
-   <AgUiRuntimeProvider>
+   <AiSdkRuntimeProvider>
      <Thread />
-   </AgUiRuntimeProvider>
+   </AiSdkRuntimeProvider>
  );
}
```

删除 `ConfirmForm` overlay 逻辑（confirm 现在通过 tool call 渲染）。

---

## 阶段 6：Agent 工具 → AI Elements 组件映射

### 6.1 映射表

| Agent 工具 | 触发条件 | AI Elements 组件 | 渲染数据来源 |
|---|---|---|---|
| `kb_retrieval` | 知识库查询完成 | `<Sources>` + 内嵌片段列表 | tool_result.result (结构化 JSON) |
| `skill__*` (含 chart_data) | 技能执行完成 | `<Tool>` + 内嵌 ChartCard (保留 recharts) | tool_result.result |
| `mcp__*` | MCP 工具执行完成 | `<Tool>` + `<CodeBlock>` / `<SchemaDisplay>` | tool_result.result |
| `confirm_action` | Agent 需要确认 | `<Confirmation>` | tool_call.args |
| `show_plan` | Agent 要展示计划 | `<Plan>` | tool_call.args / tool_result.result |
| `show_code` | Agent 要展示代码 | `<CodeBlock>` | tool_result.result |
| 通用 fallback | 其他工具 | `<Tool>` (AI Elements 原生) | tool_call.args + tool_result |

### 6.2 工具渲染器示例

```tsx
// src/components/assistant-ui/tool-renderers/kb-retrieval.tsx
import { Sources } from "@/components/ai-elements/sources";
import { Tool } from "@/components/ai-elements/tool";

export function KbRetrievalRenderer({ args, result, status }) {
  return (
    <Tool name="知识库检索" status={status}>
      <Sources sources={result?.sources ?? []} />
    </Tool>
  );
}
```

```tsx
// src/components/assistant-ui/tool-renderers/confirm-action.tsx
import { Confirmation } from "@/components/ai-elements/confirmation";

export function ConfirmActionRenderer({ args, approval, respondToApproval }) {
  if (approval?.approved === undefined) {
    return (
      <Confirmation
        title={args.action ?? "确认操作"}
        message={args.description}
        onConfirm={() => respondToApproval({ approved: true })}
        onCancel={() => respondToApproval({ approved: false, reason: "用户取消" })}
      />
    );
  }
  // 已确认/取消状态...
}
```

---

## 阶段 7：删除旧系统

### 7.1 删除文件

```bash
# 旧的 SSE 聊天页面
rm src/app/(main)/chat/page.tsx
rm src/lib/hooks/useChatStream.ts
rm src/lib/stores/chat.ts

# 旧的 AG-UI 相关
rm src/components/assistant-ui/ag-ui-runtime-provider.tsx
rm src/components/assistant-ui/confirm-form.tsx  # 被 AI Elements Confirmation 替代

# 旧的手写 ai-elements 组件（已被 CLI 安装的覆盖）
rm src/components/ai-elements/actions.tsx
rm src/components/ai-elements/response.tsx
rm src/components/ai-elements/conversation.tsx  # 被 AI Elements 版覆盖
rm src/components/ai-elements/message.tsx       # 被 AI Elements 版覆盖
rm src/components/ai-elements/prompt-input.tsx  # 被 AI Elements 版覆盖
rm src/components/ai-elements/reasoning.tsx     # 被 AI Elements 版覆盖
rm src/components/ai-elements/tool.tsx          # 被 AI Elements 版覆盖
rm src/components/ai-elements/code-block.tsx    # 被 AI Elements 版覆盖
```

### 7.2 路由重定向

`/chat` → **重定向到** `/assistant`（或直接让 `/assistant` 成为唯一聊天入口）

---

## 阶段 8：后端 Agent 适配

### 8.1 Agent 需要新增的工具

为了让 Agent 能"自主选择 AI Elements 组件"，Agent 需要知道有哪些组件可用：

**方案**：在 Agent 的 system prompt 中注入可用组件列表，Agent 通过 tool call 来"请求渲染组件"。

```python
# 伪代码：Agent system prompt 追加
AI_ELEMENTS_TOOLS_PROMPT = """
你可以使用以下工具来展示结构化内容：

- show_plan(steps: list[{title, description, status}]): 展示执行计划
- show_code(language: str, code: str, filename?: str): 展示代码块
- show_file_tree(tree: list[{path, type}]): 展示文件树
- confirm_action(action: str, description: str, fields?: list): 请求用户确认操作

当你的回答涉及多步骤计划时，使用 show_plan。
当用户要求查看/编写代码时，使用 show_code。
当你需要用户确认敏感操作时，使用 confirm_action。
"""
```

### 8.2 A2UI Schema 格式调整

当前 A2UI schema 是独立 SSE event。新方案：嵌入到 tool_result.result 中。

```python
# 旧格式 (SSE)
yield {"type": "a2ui", "schema": {...}}

# 新格式 (AI SDK tool_result)
# tool_result.result 本身包含 schema
{
  "tool_name": "kb_retrieval",
  "tool_output": "...",       # 文本摘要（给 LLM 看的）
  "ui_schema": {              # 前端渲染用的（给 Thread 看的）
    "component": "Sources",
    "props": { "sources": [...] }
  }
}
```

### 8.3 需要改动的文件

| 文件 | 改动 |
|---|---|
| `backend/app/api/aisdk.py` | 新建 |
| `backend/app/agent/executor.py` | 可能需要小改：tool_result 格式增强（附带 ui_schema） |
| `backend/app/a2ui/renderer.py` | 输出格式适配（`schema` 嵌入 `result` 而非独立 emit） |
| `backend/app/agent/prompts.py` | 追加 AI Elements 工具说明 |

### 8.4 不改的文件

- `backend/app/agent/nodes/*` — 全部保持不变
- `backend/app/agent/tools.py` — 保持不变
- `backend/app/agent/state.py` — 保持不变
- `backend/app/agent/graph.py` — 保持不变
- `backend/app/core/*` — 全部保持不变
- `backend/app/api/agui.py` — 暂时保留

---

## 迁移顺序

```
1. 后端新增 AI SDK 端点       (aisdk.py)        ← 零风险，与 AG-UI 并行
2. 前端安装 AI Elements 组件   (npx CLI)         ← 覆盖手写文件
3. 前端依赖切换               (npm install/uninstall)
4. 前端 Runtime 重写          (aisdk-runtime-provider.tsx)
5. 前端 Thread 适配           (thread.tsx 改引用)
6. 工具渲染器实现             (tool-renderers/*.tsx)
7. Agent prompt 更新          (prompts.py)
8. 删除旧系统                 (清理文件)
9. 浏览器验证                 (MCP Browser DevTools)
10. 删除 AG-UI 端点           (可选，最后做)
```

---

## 风险 & 回滚

- **AG-UI 端点保留** → 如果 AI SDK 方案出问题，前端可快速回退到 `/assistant?protocol=agui`
- **Git 分支**：在 `feat/aisdk-migration` 分支上进行
- **分阶段提交**：每个阶段单独 commit，方便 review 和回滚