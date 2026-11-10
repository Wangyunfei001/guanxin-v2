import { z } from "zod"

import type { ResearchData, WorkflowData } from "@/types"

/**
 * 驱动渲染的两个 envelope 的运行时校验。
 *
 * TypeScript 类型只是文档：后端改了字段名，编译期发现不了，运行时才会
 * 变成「读到 undefined 然后崩溃」。这里在组件边界做一次解析，形状不对
 * 就明确提示，而不是把坏数据放进状态。
 */

const workflowStepSchema = z.object({
  step_id: z.string(),
  position: z.number().default(0),
  title: z.string().default(""),
  tool_name: z.string().default(""),
  category: z.string().optional(),
  tool_category: z.string().optional(),
  risk: z.string().default("unknown"),
  status: z.string().default("pending"),
  attempt_count: z.number().default(0),
  result: z.unknown().optional(),
  error: z.string().default(""),
})

export const workflowDataSchema = z.object({
  run_id: z.string(),
  conversation_id: z.string(),
  goal: z.string().default(""),
  summary: z.string().default(""),
  status: z.string().default("pending"),
  current_step_index: z.number().default(0),
  version: z.number().default(1),
  last_error: z.string().default(""),
  steps: z.array(workflowStepSchema).default([]),
  pending_interrupt: z
    .object({
      interrupt_id: z.string(),
      kind: z.string(),
      payload: z.record(z.string(), z.unknown()).default({}),
    })
    .nullish(),
})

const researchSourceSchema = z.object({
  source_id: z.string().default(""),
  canonical_url: z.string().default(""),
  title: z.string().default(""),
  publisher: z.string().default(""),
  snippet: z.string().default(""),
  query: z.string().default(""),
  accessed_at: z.string().default(""),
})

const researchTaskSchema = z.object({
  task_id: z.string().default(""),
  position: z.number().default(0),
  question: z.string().default(""),
  status: z.string().default("pending"),
  attempt_count: z.number().default(0),
  result_summary: z.string().default(""),
  error: z.string().default(""),
})

export const researchDataSchema = z.object({
  run_id: z.string(),
  conversation_id: z.string(),
  mode: z.string().default("quick"),
  status: z.string().default("pending"),
  goal: z.string().default(""),
  plan: z
    .object({
      summary: z.string().optional(),
      questions: z.array(z.unknown()).optional(),
    })
    .default({}),
  budget: z
    .object({
      max_rounds: z.number().default(0),
      max_searches: z.number().default(0),
      max_sources: z.number().default(0),
      timeout_seconds: z.number().default(0),
    })
    .default({ max_rounds: 0, max_searches: 0, max_sources: 0, timeout_seconds: 0 }),
  usage: z
    .object({
      search_actions: z.number().optional(),
      tool_calls: z.number().optional(),
      sources: z.number().optional(),
      input_tokens: z.number().optional(),
      output_tokens: z.number().optional(),
    })
    .default({}),
  report: z.string().default(""),
  error: z.string().default(""),
  tasks: z.array(researchTaskSchema).default([]),
  sources: z.array(researchSourceSchema).default([]),
  created_at: z.string().default(""),
  updated_at: z.string().default(""),
})

/**
 * 解析工作流数据；形状不合法时返回 null，调用方按「没有工作流」处理。
 */
export function parseWorkflowData(payload: unknown): WorkflowData | null {
  const result = workflowDataSchema.safeParse(payload)
  if (!result.success) return null
  return result.data as unknown as WorkflowData
}

/**
 * 解析研究数据；形状不合法时返回 null。
 */
export function parseResearchData(payload: unknown): ResearchData | null {
  const result = researchDataSchema.safeParse(payload)
  if (!result.success) return null
  return result.data as unknown as ResearchData
}
