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

// ============ Agent Config ============
export interface AgentConfig {
  model: string
  temperature: number
  system_prompt: string
  agent_mode: string
  available_models: string[]
  api_base: string
  tools_count: number
  skills_count: number
}

// ============ Chat Message ============
export interface ToolCall {
  name: string
  input: string
  output?: string
}

export interface ChatMessage {
  role: "user" | "assistant" | "system" | "tool"
  content: string
  reasoning?: string
  toolCalls?: ToolCall[]
  a2uiSchemas?: A2UISchema[]
  streaming?: boolean
}

// ============ SSE ============
export interface SSEEvent {
  type: "token" | "reasoning" | "tool_call" | "tool_result" | "a2ui" | "done" | "error"
  content?: string
  tool_name?: string
  tool_input?: string
  tool_output?: string
  schema?: A2UISchema
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
}

export interface MCPConnection {
  server_name: string
  status: string
  tools?: MCPTool[]
}

export interface MCPTool {
  name: string
  description: string
  inputSchema?: any
}
