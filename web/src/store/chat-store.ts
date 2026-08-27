import { create } from 'zustand'
import { fetchMessages, fetchSuggestedQuestions, interruptChat, resumeChatStream, sendChat, streamChat } from '@/api/chatbot'
import { DEFAULT_GREETING } from '@/lib/format'
import { useAuthStore } from '@/store/auth-store'
import type { ChatMessage, MessageSegment, StreamPayload, StreamSegment, SuggestedQuestion } from '@/types'

interface ChatState {
  messages: ChatMessage[]
  busy: boolean
  chatError: string | null
  awaitingHuman: boolean
  currentAbortController: AbortController | null
  suggestedQuestions: SuggestedQuestion[]
  suggestedQuestionsLoading: boolean
  setChatError: (message: string | null) => void
  setMessages: (messages: ChatMessage[]) => void
  appendMessage: (message: ChatMessage) => void
  replaceLastAssistant: (message: ChatMessage) => void
  loadSuggestedQuestions: () => Promise<void>
  clearSuggestedQuestions: () => void
  loadSessionMessages: () => Promise<void>
  startNewSession: () => Promise<void>
  sendMessage: (text: string) => Promise<void>
  stopGeneration: () => Promise<void>
  resumeChat: (customPrompt?: string) => Promise<void>
}

function isGreetingOnly(messages: ChatMessage[]) {
  return messages.length === 1
    && messages[0]?.role === 'assistant'
    && messages[0]?.content === DEFAULT_GREETING
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
  awaitingHuman: false,
  currentAbortController: null,
  suggestedQuestions: [],
  suggestedQuestionsLoading: false,

  setChatError(message) {
    set({ chatError: message })
  },

  setMessages(messages) {
    const lastMsg = messages.at(-1)
    set({
      messages,
      awaitingHuman: Boolean(lastMsg?.interrupted && !lastMsg?.manual_interrupted),
    })
    if (isGreetingOnly(messages))
      void get().loadSuggestedQuestions()
    else
      get().clearSuggestedQuestions()
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

  clearSuggestedQuestions() {
    set({ suggestedQuestions: [], suggestedQuestionsLoading: false })
  },

  async loadSuggestedQuestions() {
    const sessionToken = useAuthStore.getState().sessionToken
    if (!sessionToken) {
      set({
        suggestedQuestions: [],
        suggestedQuestionsLoading: false,
      })
      return
    }

    set({ suggestedQuestionsLoading: true })
    try {
      const data = await fetchSuggestedQuestions(sessionToken)
      const questions = data.questions || []
      if (!isGreetingOnly(get().messages)) {
        set({ suggestedQuestionsLoading: false })
        return
      }
      set({
        suggestedQuestions: questions,
        suggestedQuestionsLoading: false,
      })
    }
    catch {
      if (!isGreetingOnly(get().messages)) {
        set({ suggestedQuestionsLoading: false })
        return
      }
      set({
        suggestedQuestions: [],
        suggestedQuestionsLoading: false,
      })
    }
  },

  async loadSessionMessages() {
    const sessionToken = useAuthStore.getState().sessionToken
    if (!sessionToken) {
      get().setMessages([{ role: 'assistant', content: DEFAULT_GREETING }])
      return
    }

    try {
      const data = await fetchMessages(sessionToken)
      const msgs = data.messages || []
      get().setMessages(msgs.length ? msgs : [{ role: 'assistant', content: DEFAULT_GREETING }])
    }
    catch (error) {
      const message = error instanceof Error ? error.message : '加载历史记录失败'
      set({
        messages: [{ role: 'assistant', content: `⚠️ 加载历史记录失败: ${message}` }],
        awaitingHuman: false,
        suggestedQuestions: [],
        suggestedQuestionsLoading: false,
      })
    }
  },

  async startNewSession() {
    const auth = useAuthStore.getState()
    if (!auth.userToken) {
      auth.setAuthModalOpen(true)
      return
    }

    await auth.createSession()
    set({ chatError: null })
    get().setMessages([{ role: 'assistant', content: DEFAULT_GREETING }])
  },

  async stopGeneration() {
    const { currentAbortController, messages } = get()
    if (currentAbortController) {
      currentAbortController.abort()
    }
    const sessionToken = useAuthStore.getState().sessionToken
    if (sessionToken) {
      void interruptChat(sessionToken).catch(() => {})
    }

    const lastMsg = messages.at(-1)
    if (lastMsg && lastMsg.role === 'assistant') {
      get().replaceLastAssistant({
        ...lastMsg,
        interrupted: true,
        manual_interrupted: true,
        interrupt_question: '用户手动中断',
      })
    }

    set({
      busy: false,
      currentAbortController: null,
      awaitingHuman: false,
    })
  },

  async resumeChat(customPrompt?: string) {
    if (get().busy)
      return

    const auth = useAuthStore.getState()
    const sessionToken = auth.sessionToken
    if (!sessionToken) {
      set({ chatError: '未找到有效会话，无法恢复。' })
      return
    }

    const abortController = new AbortController()
    set({
      busy: true,
      chatError: null,
      awaitingHuman: false,
      currentAbortController: abortController,
    })

    const streamSegments: StreamSegment[] = []
    const insideThinkRef = { current: false }
    let interrupted = false
    let interruptQuestion = ''
    let manualInterrupted = false

    const currentMessages = get().messages
    const lastAssistant = currentMessages.filter(m => m.role === 'assistant').at(-1)
    if (lastAssistant?.segments && lastAssistant.segments.length > 0) {
      lastAssistant.segments.forEach((seg) => {
        streamSegments.push({
          type: seg.type,
          content: seg.content || '',
          completed: true,
          tool_name: seg.tool_name,
          tool_args: seg.tool_args,
          tool_output: seg.tool_output,
          text: seg.status,
        })
      })
    }

    const updateStreamingAssistant = () => {
      const result = segmentsToMessage(streamSegments)
      get().replaceLastAssistant({
        role: 'assistant',
        content: interrupted ? (interruptQuestion || result.content) : result.content,
        thinking: result.thinking,
        tool_calls: result.tool_calls,
        segments: result.segments,
        interrupted,
        interrupt_question: interruptQuestion,
        manual_interrupted: manualInterrupted,
      })
    }

    try {
      for await (const payload of resumeChatStream(sessionToken, customPrompt || '', abortController.signal)) {
        if (payload.interrupted) {
          interrupted = true
          manualInterrupted = Boolean(payload.manual_interrupted)
          interruptQuestion = payload.interrupt_question || payload.content || interruptQuestion
        }
        applyStreamPayload(streamSegments, payload, insideThinkRef)
        updateStreamingAssistant()
      }

      completeOpenSegments(streamSegments)
      updateStreamingAssistant()

      if (interrupted && !manualInterrupted)
        set({ awaitingHuman: true })

      window.setTimeout(() => {
        void auth.loadSessions()
      }, 1200)
    }
    catch (error) {
      if (abortController.signal.aborted) {
        return
      }
      const message = error instanceof Error ? error.message : '恢复失败'
      get().replaceLastAssistant({
        ...(lastAssistant || { role: 'assistant', content: '' }),
        content: `${lastAssistant?.content || ''}\n\n❌ **恢复失败**: ${message}`,
      })
      set({ chatError: message, awaitingHuman: false })
    }
    finally {
      set({ busy: false, currentAbortController: null })
    }
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

    get().clearSuggestedQuestions()

    const isResuming = get().awaitingHuman
    const streamSegments: StreamSegment[] = []
    const insideThinkRef = { current: false }
    let hasReceivedAnyToken = false
    let interrupted = false
    let interruptQuestion = ''
    let manualInterrupted = false

    const abortController = new AbortController()

    if (isResuming) {
      const currentMessages = get().messages
      const lastAssistant = currentMessages.filter(m => m.role === 'assistant').at(-1)
      if (lastAssistant?.segments && lastAssistant.segments.length > 0) {
        lastAssistant.segments.forEach((seg) => {
          if (seg.type === 'tool_call' && seg.tool_name === 'ask_human' && !seg.tool_output) {
            streamSegments.push({
              type: 'tool_call',
              content: '',
              text: '✅ 已完成决策确认',
              completed: true,
              tool_name: 'ask_human',
              tool_args: seg.tool_args,
              tool_output: content,
            })
          }
          else {
            streamSegments.push({
              type: seg.type,
              content: seg.content || '',
              completed: true,
              tool_name: seg.tool_name,
              tool_args: seg.tool_args,
              tool_output: seg.tool_output,
              text: seg.status,
            })
          }
        })
      }

      const hasInterruptSeg = streamSegments.some(s => s.tool_name === 'ask_human')
      if (!hasInterruptSeg && lastAssistant?.interrupted) {
        streamSegments.push({
          type: 'tool_call',
          content: '',
          text: '✅ 已完成决策确认',
          completed: true,
          tool_name: 'ask_human',
          tool_args: lastAssistant.interrupt_question || lastAssistant.content || '',
          tool_output: content,
        })
      }

      set({ busy: true, chatError: null, awaitingHuman: false, currentAbortController: abortController })
      const initResult = segmentsToMessage(streamSegments)
      get().replaceLastAssistant({
        role: 'assistant',
        content: initResult.content,
        thinking: initResult.thinking,
        tool_calls: initResult.tool_calls,
        segments: initResult.segments,
        interrupted: false,
        interrupt_question: '',
        manual_interrupted: false,
      })
    }
    else {
      set({ busy: true, chatError: null, awaitingHuman: false, currentAbortController: abortController })
      get().appendMessage({ role: 'user', content })
      get().appendMessage({ role: 'assistant', content: '', segments: [] })
    }

    const updateStreamingAssistant = () => {
      const result = segmentsToMessage(streamSegments)
      get().replaceLastAssistant({
        role: 'assistant',
        content: interrupted ? (interruptQuestion || result.content) : result.content,
        thinking: result.thinking,
        tool_calls: result.tool_calls,
        segments: result.segments,
        interrupted,
        interrupt_question: interruptQuestion,
        manual_interrupted: manualInterrupted,
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

      for await (const payload of streamChat(sessionToken, content, abortController.signal)) {
        if (payload.thinking || payload.content)
          hasReceivedAnyToken = true
        if (payload.interrupted) {
          interrupted = true
          manualInterrupted = Boolean(payload.manual_interrupted)
          interruptQuestion = payload.interrupt_question || payload.content || interruptQuestion
        }
        applyStreamPayload(streamSegments, payload, insideThinkRef)
        updateStreamingAssistant()
      }

      completeOpenSegments(streamSegments)
      updateStreamingAssistant()

      const result = segmentsToMessage(streamSegments)
      if (!hasReceivedAnyToken && !result.content && !result.thinking && !interrupted) {
        const data = await sendChat(sessionToken, [{ role: 'user', content }])
        const assistantMessages = (data.messages || []).filter(item => item.role === 'assistant')
        const lastMsg = assistantMessages.at(-1)
        if (lastMsg) {
          interrupted = Boolean(lastMsg.interrupted)
          manualInterrupted = Boolean(lastMsg.manual_interrupted)
          interruptQuestion = lastMsg.interrupt_question || lastMsg.content || ''
          get().replaceLastAssistant(lastMsg)
        }
      }

      if (interrupted && !manualInterrupted)
        set({ awaitingHuman: true })

      window.setTimeout(() => {
        void auth.loadSessions()
      }, 1200)
    }
    catch (error) {
      if (abortController.signal.aborted) {
        return
      }
      const message = error instanceof Error ? error.message : '发送失败'
      get().replaceLastAssistant({ role: 'assistant', content: `❌ **出错了**: ${message}` })
      set({ chatError: message, awaitingHuman: false })
    }
    finally {
      set({ busy: false, currentAbortController: null })
    }
  },
}))

export type { StreamSegment }

