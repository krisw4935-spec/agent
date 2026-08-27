import { create } from 'zustand'
import { fetchMessages, sendChat, streamChat } from '@/api/chatbot'
import { DEFAULT_GREETING } from '@/lib/format'
import { useAuthStore } from '@/store/auth-store'
import type { ChatMessage, MessageSegment, StreamPayload, StreamSegment } from '@/types'

interface ChatState {
  messages: ChatMessage[]
  busy: boolean
  chatError: string | null
  setChatError: (message: string | null) => void
  setMessages: (messages: ChatMessage[]) => void
  appendMessage: (message: ChatMessage) => void
  replaceLastAssistant: (message: ChatMessage) => void
  loadSessionMessages: () => Promise<void>
  startNewSession: () => Promise<void>
  sendMessage: (text: string) => Promise<void>
}

function completeOpenSegments(segments: StreamSegment[]) {
  segments.forEach((segment) => {
    if (!segment.completed) {
      segment.completed = true
      if (segment.type === 'thinking' && segment.startTime)
        segment.elapsed = Math.max(1, Math.round((Date.now() - segment.startTime) / 1000))
    }
  })
}

function applyStreamPayload(segments: StreamSegment[], payload: StreamPayload, insideThinkRef: { current: boolean }) {
  if (payload.thinking)
    appendThinkingSegment(segments, payload.thinking)

  if (payload.status) {
    addOrUpdateStatusSegment(
      segments,
      payload.status,
      payload.tool_name,
      payload.tool_args,
      payload.tool_output,
    )
  }

  if (payload.content)
    appendContentSegment(segments, payload.content, insideThinkRef)
}

function appendThinkingSegment(segments: StreamSegment[], chunk: string) {
  const lastSeg = segments[segments.length - 1]
  let thinkSeg: StreamSegment

  if (lastSeg?.type === 'thinking' && !lastSeg.completed)
    thinkSeg = lastSeg
  else {
    completeOpenSegments(segments)
    thinkSeg = {
      type: 'thinking',
      content: '',
      completed: false,
      startTime: Date.now(),
      elapsed: 0,
    }
    segments.push(thinkSeg)
  }

  thinkSeg.content += chunk
}

function addOrUpdateStatusSegment(
  segments: StreamSegment[],
  statusText: string,
  toolName = '',
  toolArgs = '',
  toolOutput = '',
) {
  if (!statusText)
    return

  if (!toolName && !statusText.startsWith('✅') && !statusText.includes('运算完成'))
    return

  const isCompletedMsg = statusText.startsWith('✅') || statusText.includes('完成')

  segments.forEach((segment) => {
    if (segment.type === 'thinking' && !segment.completed) {
      segment.completed = true
      if (segment.startTime)
        segment.elapsed = Math.max(1, Math.round((Date.now() - segment.startTime) / 1000))
    }
  })

  const lastSeg = segments[segments.length - 1]
  if (lastSeg?.type === 'tool_call' && (lastSeg.tool_name === toolName || (!lastSeg.completed && !lastSeg.tool_name))) {
    lastSeg.text = statusText
    if (toolName)
      lastSeg.tool_name = toolName
    if (toolArgs)
      lastSeg.tool_args = toolArgs
    if (toolOutput)
      lastSeg.tool_output = toolOutput
    if (isCompletedMsg)
      lastSeg.completed = true
    return
  }

  segments.forEach((segment) => {
    if (segment.type === 'tool_call')
      segment.completed = true
  })

  segments.push({
    type: 'tool_call',
    content: '',
    text: statusText,
    completed: isCompletedMsg,
    tool_name: toolName,
    tool_args: toolArgs,
    tool_output: toolOutput,
  })
}

function appendContentSegment(segments: StreamSegment[], rawChunk: string, insideThinkRef: { current: boolean }) {
  if (!rawChunk)
    return

  let chunk = rawChunk
  if (chunk.includes('<think>')) {
    insideThinkRef.current = true
    const parts = chunk.split('<think>')
    if (parts[0])
      appendContentSegment(segments, parts[0], insideThinkRef)
    chunk = parts[1] || ''
  }

  if (insideThinkRef.current) {
    if (chunk.includes('</think>')) {
      insideThinkRef.current = false
      const parts = chunk.split('</think>')
      appendThinkingSegment(segments, parts[0])
      if (parts[1])
        appendContentSegment(segments, parts[1], insideThinkRef)
      return
    }
    appendThinkingSegment(segments, chunk)
    return
  }

  completeOpenSegments(segments)
  const lastSeg = segments[segments.length - 1]
  if (lastSeg?.type === 'text')
    lastSeg.content += chunk
  else
    segments.push({ type: 'text', content: chunk, completed: true })
}

function segmentsToMessage(segments: StreamSegment[]): Pick<ChatMessage, 'content' | 'thinking' | 'tool_calls' | 'segments'> {
  // Do NOT complete open segments here — this runs on every stream token.
  // Premature completion causes each thinking chunk to start a new block.

  const thinkParts = segments.filter(item => item.type === 'thinking' && item.content).map(item => item.content.trim())
  const textParts = segments.filter(item => item.type === 'text' && item.content).map(item => item.content.trim())
  const toolCallsList = segments
    .filter(item => item.type === 'tool_call')
    .map(item => ({
      tool_name: item.tool_name || '',
      tool_args: item.tool_args || '',
      tool_output: item.tool_output || '',
      status: item.text || '',
    }))

  const formattedSegments: MessageSegment[] = segments
    .filter(segment => segment.type !== 'thinking' || Boolean(segment.content.trim()))
    .map((segment) => {
      if (segment.type === 'thinking')
        return { type: 'thinking', content: segment.content }
      if (segment.type === 'tool_call') {
        return {
          type: 'tool_call',
          tool_name: segment.tool_name,
          tool_args: segment.tool_args,
          tool_output: segment.tool_output,
          status: segment.text,
        }
      }
      return { type: 'text', content: segment.content }
    })

  return {
    content: textParts.join('\n\n'),
    thinking: thinkParts.join('\n\n'),
    tool_calls: toolCallsList,
    segments: formattedSegments,
  }
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  busy: false,
  chatError: null,

  setChatError(message) {
    set({ chatError: message })
  },

  setMessages(messages) {
    set({ messages })
  },

  appendMessage(message) {
    set({ messages: [...get().messages, message] })
  },

  replaceLastAssistant(message) {
    const messages = [...get().messages]
    const lastIndex = messages.length - 1
    if (lastIndex >= 0 && messages[lastIndex].role === 'assistant')
      messages[lastIndex] = message
    else
      messages.push(message)
    set({ messages })
  },

  async loadSessionMessages() {
    const sessionToken = useAuthStore.getState().sessionToken
    if (!sessionToken) {
      set({ messages: [{ role: 'assistant', content: DEFAULT_GREETING }] })
      return
    }

    try {
      const data = await fetchMessages(sessionToken)
      const msgs = data.messages || []
      set({ messages: msgs.length ? msgs : [{ role: 'assistant', content: DEFAULT_GREETING }] })
    }
    catch (error) {
      const message = error instanceof Error ? error.message : '加载历史记录失败'
      set({ messages: [{ role: 'assistant', content: `⚠️ 加载历史记录失败: ${message}` }] })
    }
  },

  async startNewSession() {
    const auth = useAuthStore.getState()
    if (!auth.userToken) {
      auth.setAuthModalOpen(true)
      return
    }

    await auth.createSession()
    set({
      messages: [{ role: 'assistant', content: DEFAULT_GREETING }],
      chatError: null,
    })
  },

  async sendMessage(text) {
    const content = text.trim()
    if (!content || get().busy)
      return

    const auth = useAuthStore.getState()
    if (!auth.userToken) {
      set({ chatError: '请先登录账号后再发送数学问题。' })
      auth.setAuthModalOpen(true)
      return
    }

    set({ busy: true, chatError: null })
    get().appendMessage({ role: 'user', content })
    get().appendMessage({ role: 'assistant', content: '', segments: [] })

    const streamSegments: StreamSegment[] = []
    const insideThinkRef = { current: false }
    let hasReceivedAnyToken = false

    const updateStreamingAssistant = () => {
      const result = segmentsToMessage(streamSegments)
      get().replaceLastAssistant({
        role: 'assistant',
        content: result.content,
        thinking: result.thinking,
        tool_calls: result.tool_calls,
        segments: result.segments,
      })
    }

    updateStreamingAssistant()

    try {
      let sessionToken = auth.sessionToken
      if (!sessionToken) {
        const session = await auth.createSession()
        const createdToken = session.token?.access_token
        if (!createdToken)
          throw new Error('无法创建会话')
        sessionToken = createdToken
      }

      for await (const payload of streamChat(sessionToken, content)) {
        if (payload.thinking || payload.content)
          hasReceivedAnyToken = true
        applyStreamPayload(streamSegments, payload, insideThinkRef)
        updateStreamingAssistant()
      }

      completeOpenSegments(streamSegments)
      updateStreamingAssistant()

      const result = segmentsToMessage(streamSegments)
      if (!hasReceivedAnyToken && !result.content && !result.thinking) {
        const data = await sendChat(sessionToken, [{ role: 'user', content }])
        const assistantMessages = (data.messages || []).filter(item => item.role === 'assistant')
        const lastMsg = assistantMessages.at(-1)
        if (lastMsg)
          get().replaceLastAssistant(lastMsg)
      }

      window.setTimeout(() => {
        void auth.loadSessions()
      }, 1200)
    }
    catch (error) {
      const message = error instanceof Error ? error.message : '发送失败'
      get().replaceLastAssistant({ role: 'assistant', content: `❌ **出错了**: ${message}` })
      set({ chatError: message })
    }
    finally {
      set({ busy: false })
    }
  },
}))

export type { StreamSegment }
