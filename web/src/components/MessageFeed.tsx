import { useEffect, useRef } from 'react'
import { useChatStore } from '@/store/chat-store'
import { MessageRow } from '@/components/MessageRow'
import { SuggestedQuestions } from '@/components/SuggestedQuestions'
import { useImageModalStore } from '@/store/image-modal-store'
import { DEFAULT_GREETING } from '@/lib/format'

export function MessageFeed() {
  const messages = useChatStore(state => state.messages)
  const busy = useChatStore(state => state.busy)
  const suggestedQuestions = useChatStore(state => state.suggestedQuestions)
  const suggestedQuestionsLoading = useChatStore(state => state.suggestedQuestionsLoading)
  const feedRef = useRef<HTMLDivElement>(null)
  const openImage = useImageModalStore(state => state.open)

  const showSuggestions = messages.length === 1
    && messages[0]?.role === 'assistant'
    && messages[0]?.content === DEFAULT_GREETING
    && (suggestedQuestionsLoading || suggestedQuestions.length > 0)

  useEffect(() => {
    const node = feedRef.current
    if (node)
      node.scrollTop = node.scrollHeight
  }, [messages, busy, suggestedQuestions, suggestedQuestionsLoading])

  return (
    <div
      ref={feedRef}
      className="flex-1 overflow-y-auto p-6"
      aria-live="polite"
      onClick={(event) => {
        const target = event.target
        if (target instanceof HTMLImageElement)
          openImage(target.src)
      }}
    >
      <div className="flex flex-col gap-5 max-w-860px mx-auto">
        {messages.map((message, index) => (
          <MessageRow
            key={`${message.role}-${index}-${message.content.slice(0, 24)}`}
            message={message}
            streaming={busy && index === messages.length - 1 && message.role === 'assistant'}
          />
        ))}
        {showSuggestions ? <SuggestedQuestions /> : null}
      </div>
    </div>
  )
}
