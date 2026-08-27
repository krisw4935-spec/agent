export interface User {
  id: string
  email: string
  username?: string | null
}

export interface TokenResponse {
  access_token: string
  token_type?: string
}

export interface SessionRecord {
  session_id: string
  name?: string | null
  created_at?: string | null
  token?: { access_token: string }
}

export interface GuestSessionResponse extends SessionRecord {
  token: { access_token: string }
}

export interface RegisterResponse {
  id: string
  email: string
  username?: string | null
  token: { access_token: string }
}

export interface ToolCall {
  tool_name: string
  tool_args?: string
  tool_output?: string
  status?: string
}

export interface MessageSegment {
  type: 'thinking' | 'tool_call' | 'text'
  content?: string
  tool_name?: string
  tool_args?: string
  tool_output?: string
  status?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  thinking?: string
  tool_calls?: ToolCall[]
  segments?: MessageSegment[]
  interrupted?: boolean
  interrupt_question?: string
}

export interface StreamPayload {
  content?: string
  thinking?: string
  status?: string
  tool_name?: string
  tool_args?: string
  tool_output?: string
  done?: boolean
  interrupted?: boolean
  interrupt_question?: string
}

export interface StreamSegment {
  type: 'thinking' | 'tool_call' | 'text'
  content: string
  completed: boolean
  startTime?: number
  elapsed?: number
  text?: string
  tool_name?: string
  tool_args?: string
  tool_output?: string
}
