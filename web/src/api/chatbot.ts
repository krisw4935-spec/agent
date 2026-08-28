import { API_BASE, api } from '@/api/client'
import type { ChatMessage, InterruptResponse, StreamPayload, SuggestedQuestion } from '@/types'

interface MessagesResponse {
  messages: ChatMessage[]
}

interface ChatResponse {
  messages: ChatMessage[]
}

export interface SuggestedQuestionsStreamPayload {
  questions?: SuggestedQuestion[]
  status?: string
  error?: string
  done?: boolean
}

export function fetchMessages(token: string, timeoutMs = 6000) {
  return api<MessagesResponse>('/chatbot/messages', { token, timeoutMs })
}

export async function* streamSuggestedQuestions(
  token: string,
  signal?: AbortSignal,
): AsyncGenerator<SuggestedQuestionsStreamPayload> {
  const response = await fetch(`${API_BASE}/chatbot/suggested-questions`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'text/event-stream',
    },
    signal,
  })

  if (!response.ok) {
    const errBody = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(errBody.detail || `推荐问题请求失败 (${response.status})`)
  }

  const reader = response.body?.getReader()
  if (!reader)
    throw new Error('推荐问题流式响应不可用')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done)
      break

    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() || ''

    for (const chunk of chunks) {
      const data = chunk
        .split('\n')
        .filter(line => line.startsWith('data: '))
        .map(line => line.slice(6))
        .join('\n')
      if (!data)
        continue

      const payload = JSON.parse(data) as SuggestedQuestionsStreamPayload
      if (payload.error)
        throw new Error(payload.error)
      yield payload
    }
  }

  if (buffer.trim()) {
    const data = buffer
      .split('\n')
      .filter(line => line.startsWith('data: '))
      .map(line => line.slice(6))
      .join('\n')
    if (data) {
      const payload = JSON.parse(data) as SuggestedQuestionsStreamPayload
      if (payload.error)
        throw new Error(payload.error)
      yield payload
    }
  }
}

export function sendChat(token: string, messages: Pick<ChatMessage, 'role' | 'content'>[]) {
  return api<ChatResponse>('/chatbot/chat', {
    method: 'POST',
    token,
    body: { messages },
  })
}

export function interruptChat(token: string) {
  return api<InterruptResponse>('/chatbot/chat/interrupt', {
    method: 'POST',
    token,
  })
}

export async function* streamChat(token: string, content: string, signal?: AbortSignal): AsyncGenerator<StreamPayload> {
  const response = await fetch(`${API_BASE}/chatbot/chat/stream`, {
    method: 'POST',
    signal,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ messages: [{ role: 'user', content }] }),
  })

  if (!response.ok) {
    const errBody = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(errBody.detail || `发送失败 (${response.status})`)
  }

  const reader = response.body?.getReader()
  if (!reader)
    throw new Error('流式响应不可用')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done)
      break

    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() || ''

    for (const chunk of chunks) {
      const line = chunk.split('\n').find(item => item.startsWith('data: '))
      if (!line)
        continue
      try {
        yield JSON.parse(line.slice(6)) as StreamPayload
      }
      catch {
        // ignore malformed chunks
      }
    }
  }
}

export async function* resumeChatStream(token: string, prompt = '', signal?: AbortSignal): AsyncGenerator<StreamPayload> {
  const response = await fetch(`${API_BASE}/chatbot/chat/resume`, {
    method: 'POST',
    signal,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ prompt }),
  })

  if (!response.ok) {
    const errBody = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(errBody.detail || `恢复失败 (${response.status})`)
  }

  const reader = response.body?.getReader()
  if (!reader)
    throw new Error('流式响应不可用')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done)
      break

    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() || ''

    for (const chunk of chunks) {
      const line = chunk.split('\n').find(item => item.startsWith('data: '))
      if (!line)
        continue
      try {
        yield JSON.parse(line.slice(6)) as StreamPayload
      }
      catch {
        // ignore malformed chunks
      }
    }
  }
}

