
// ============ API Response ============
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

// ============ Auth ============
export interface User {
  user_id: string
  username: string
  tenant_id: string
  tenant_name: string
  role: "admin" | "user"
  display_name: string
  created_at: string
}

export interface LoginResult {
  access_token: string
  token_type: string
  user: User
}

// ============ Conversation ============
export interface Conversation {
  conversation_id: string
  title: string
  agent_id: string
  created_at: string
  updated_at: string
  message_count?: number
}

export interface ConversationMessage {
  message_id: string
  role: "user" | "assistant" | "system"
  content: string
  reasoning: string
  tool_calls: Record<string, unknown>[]
  a2ui_schemas: A2UISchema[]
  parts: Record<string, any>[]
  created_at: string
}

export interface ConversationDetail extends Conversation {
  tenant_id: string
  user_id: string
  messages: ConversationMessage[]
}

// ============ Agent Config ============
export interface AgentConfig {
  agent_id: string
  tenant_id: string
  name: string
  model: string
  temperature: number
  max_tokens: number
  system_prompt: string
  enabled_tools: string[]
  enabled_skills: string[]
  mcp_servers: string[]
  agent_mode: string
  available_models: string[]
  available_tools: string[]
  available_skills: SkillMetadata[]
  available_mcp_servers: string[]
  api_base: string
  tools_count: number
  skills_count: number
  available_tool_specs: ToolSpec[]
}

export interface ToolSpec {
  name: string
  display_name: string
  description: string
  input_schema: Record<string, unknown>
  source_type: "builtin" | "skill" | "mcp" | "provider"
  source_name: string
  effect: "read" | "write" | "unknown"
  approval_required: boolean
  enabled: boolean
}

// ============ Persistent Workflows ============
export type WorkflowStatus =
  | "planning"
  | "running"
  | "waiting_input"
  | "waiting_approval"
  | "uncertain"
  | "completed"
  | "failed"
  | "cancelled"

export interface WorkflowStep {
  step_id: string
  position: number
  title: string
  tool_name: string
  category?: string
  tool_category?: string
  risk: "read" | "write" | "unknown"
  status: string
  attempt_count: number
  result: unknown
  error: string
}

export interface WorkflowData {
  run_id: string
  conversation_id: string
  goal: string
  summary: string
  status: WorkflowStatus
  current_step_index: number
  version: number
  last_error: string
  steps: WorkflowStep[]
  pending_interrupt?: {
    interrupt_id: string
    kind: "input" | "approval" | "recovery"
    payload: Record<string, unknown>
  } | null
  created_at?: string
  updated_at?: string
}

export type GuanxinDataParts = {
  workflow: WorkflowData
  a2ui: { schema: A2UISchema; toolCallId?: string }
  research: ResearchData
}

export interface HistoricalMessage {
  id: string
  role: "user" | "assistant"
  parts: Record<string, any>[]
}

// ============ A2UI ============
export interface A2UISchema {
  component_type:
    | "form_card"
    | "info_card"
    | "list_card"
    | "confirm_card"
    | "chart_card"
    | string
  props: Record<string, any>
  children?: A2UISchema[]
}

// ============ Knowledge Base ============
export interface Document {
  doc_id: string
  tenant_id: string
  filename: string
  file_type: string
  file_size: number
  title: string
  status: string
  chunk_count: number
  error_message: string
  created_at: string
  updated_at: string
}

export interface DocumentChunk {
  chunk_id: string
  content: string
  text?: string
  score?: number
  metadata?: Record<string, any>
}

export interface DocumentDetail extends Document {
  chunks?: DocumentChunk[]
}

export interface RetrievalResult {
  chunk_id: string
  content: string
  score: number
  doc_id: string
  filename: string
}

// ============ Skill ============
export interface SkillParam {
  name: string
  type: string
  description: string
  required: boolean
  default?: any
  options?: string[]
  label?: string
}

export interface SkillMetadata {
  name: string
  display_name: string
  description: string
  skill_type: string
  status: string
  version: string
  params: SkillParam[]
  tags: string[]
  category: string
}

// ============ MCP ============
export interface MCPServer {
  name: string
  command: string
  args: string[]
  env: Record<string, string>
  description: string
  status: string
  registered?: boolean
  runtime_status?: string
  agent_enabled?: boolean
}

export interface MCPConnection {
  server_name: string
  status: string
  tools?: MCPTool[]
  error?: string
  agent_enabled?: boolean
}

export interface MCPTool {
  name: string
  description: string
  input_schema?: Record<string, unknown>
  annotations?: Record<string, unknown>
  policy?: MCPToolPolicy | null
}

export interface MCPToolPolicy {
  tenant_id: string
  server_name: string
  tool_name: string
  enabled: boolean
  effect: "read" | "write" | "unknown"
  approval_required: boolean
}

// ============ Deep Research ============
export type ResearchStatus =
  | "planning"
  | "searching"
  | "analyzing"
  | "synthesizing"
  | "completed"
  | "failed"
  | "cancelled"
  | "interrupted"

export interface ResearchTask {
  task_id: string
  position: number
  question: string
  status: string
  attempt_count: number
  result_summary: string
  error: string
}

export interface ResearchSource {
  source_id: string
  canonical_url: string
  title: string
  publisher: string
  snippet: string
  query: string
  accessed_at: string
}

export interface ResearchData {
  run_id: string
  conversation_id: string
  mode: "quick" | "deep"
  status: ResearchStatus
  goal: string
  plan: { summary?: string; questions?: unknown[] }
  budget: {
    max_rounds: number
    max_searches: number
    max_sources: number
    timeout_seconds: number
  }
  usage: {
    search_actions?: number
    tool_calls?: number
    sources?: number
    input_tokens?: number
    output_tokens?: number
  }
  report: string
  error: string
  tasks: ResearchTask[]
  sources: ResearchSource[]
  created_at: string
  updated_at: string
}
