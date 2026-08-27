import { useCallback, useRef } from 'react'
import { Avatar, Button, Toast } from '@douyinfe/semi-ui-19'
import { IconCopy } from '@douyinfe/semi-icons'
import type { ChatMessage } from '@/types'
import { AssistantContent } from '@/components/AssistantContent'

interface MessageRowProps {
  message: ChatMessage
  streaming?: boolean
}

export function MessageRow({ message, streaming = false }: MessageRowProps) {
  const bodyRef = useRef<HTMLDivElement>(null)
  const isUser = message.role === 'user'

  const handleCopy = useCallback(async () => {
    const textBlocks = bodyRef.current?.querySelectorAll('.markdown-body') || []
    let textToCopy = ''
    if (textBlocks.length > 0)
      textToCopy = Array.from(textBlocks).map(block => block.textContent || '').join('\n\n')
    else
      textToCopy = message.content

    await navigator.clipboard.writeText(textToCopy)
    Toast.success('已复制到剪贴板')
  }, [message.content])

  return (
    <div className={`message-row ${message.role}`}>
      <Avatar
        color={isUser ? 'blue' : 'green'}
        size="medium"
        style={{ flexShrink: 0 }}
      >
        {isUser ? '生' : '师'}
      </Avatar>
      <div className="message-body" ref={bodyRef}>
        <div className="message-bubble">
          {isUser
            ? message.content
            : (
                <AssistantContent
                  content={message.content}
                  thinking={message.thinking}
                  toolCalls={message.tool_calls}
                  segments={message.segments}
                  streaming={streaming}
                />
              )}
        </div>
        {!isUser && message.content
          ? (
              <div className="message-actions">
                <Button
                  theme="borderless"
                  type="tertiary"
                  size="small"
                  icon={<IconCopy />}
                  onClick={() => void handleCopy()}
                >
                  复制
                </Button>
              </div>
            )
          : null}
      </div>
    </div>
  )
}
