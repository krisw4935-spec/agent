import { API_BASE, api } from '@/api/client'
import type { ChatMessage, StreamPayload } from '@/types'

interface MessagesResponse {
  messages: ChatMessage[]
}

interface ChatResponse {
  messages: ChatMessage[]
}

export function fetchMessages(token: string, timeoutMs = 6000) {
  return api<MessagesResponse>('/chatbot/messages', { token, timeoutMs })
}

export function sendChat(token: string, messages: Pick<ChatMessage, 'role' | 'content'>[]) {
  return api<ChatResponse>('/chatbot/chat', {
    method: 'POST',
    token,
    body: { messages },
  })
}

export async function* streamChat(token: string, content: string): AsyncGenerator<StreamPayload> {
  const response = await fetch(`${API_BASE}/chatbot/chat/stream`, {
    method: 'POST',
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
