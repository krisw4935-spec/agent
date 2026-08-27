import { useEffect, useRef } from 'react'
import { useChatStore } from '@/store/chat-store'
import { MessageRow } from '@/components/MessageRow'
import { useImageModalStore } from '@/store/image-modal-store'

export function MessageFeed() {
  const messages = useChatStore(state => state.messages)
  const busy = useChatStore(state => state.busy)
  const feedRef = useRef<HTMLDivElement>(null)
  const openImage = useImageModalStore(state => state.open)

  useEffect(() => {
    const node = feedRef.current
    if (node)
      node.scrollTop = node.scrollHeight
  }, [messages, busy])

  return (
    <div
      ref={feedRef}
      className="message-scroll"
      aria-live="polite"
      onClick={(event) => {
        const target = event.target
        if (target instanceof HTMLImageElement)
          openImage(target.src)
      }}
    >
      <div className="message-list">
        {messages.map((message, index) => (
          <MessageRow
            key={`${message.role}-${index}-${message.content.slice(0, 24)}`}
            message={message}
            streaming={busy && index === messages.length - 1 && message.role === 'assistant'}
          />
        ))}
      </div>
    </div>
  )
}
