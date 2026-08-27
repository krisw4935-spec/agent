import { useCallback, useEffect, useRef, useState } from 'react'
import { Avatar, Button, Toast } from '@douyinfe/semi-ui-19'
import clsx from 'clsx'
import type { ChatMessage } from '@/types'
import { AssistantContent } from '@/components/AssistantContent'
import { HumanInterruptCard } from '@/components/HumanInterruptCard'

interface MessageRowProps {
  message: ChatMessage
  streaming?: boolean
}

export function MessageRow({ message, streaming = false }: MessageRowProps) {
  const bodyRef = useRef<HTMLDivElement>(null)
  const copyResetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [isCopied, setIsCopied] = useState(false)
  const isUser = message.role === 'user'
  const isInterrupted = Boolean(message.interrupted)
  const interruptQuestion = message.interrupt_question || message.content
  const priorSegments = (message.segments || []).filter(
    segment => segment.type === 'thinking' || segment.type === 'tool_call',
  )

  useEffect(() => {
    return () => {
      if (copyResetTimerRef.current)
        clearTimeout(copyResetTimerRef.current)
    }
  }, [])

  const handleCopy = useCallback(async () => {
    const textBlocks = bodyRef.current?.querySelectorAll('.markdown-body') || []
    let textToCopy = ''
    if (isInterrupted)
      textToCopy = interruptQuestion
    else if (textBlocks.length > 0)
      textToCopy = Array.from(textBlocks).map(block => block.textContent || '').join('\n\n')
    else
      textToCopy = message.content

    try {
      await navigator.clipboard.writeText(textToCopy)
      setIsCopied(true)
      Toast.success('已复制到剪贴板')
      if (copyResetTimerRef.current)
        clearTimeout(copyResetTimerRef.current)
      copyResetTimerRef.current = setTimeout(() => setIsCopied(false), 2000)
    }
    catch {
      Toast.error('复制失败，请重试')
    }
  }, [interruptQuestion, isInterrupted, message.content])

  return (
    <div className={clsx('flex gap-3 items-start', isUser && 'flex-row-reverse')}>
      <Avatar
        color={isUser ? 'blue' : 'green'}
        size="medium"
        className="shrink-0"
      >
        {isUser ? '生' : '师'}
      </Avatar>
      <div
        ref={bodyRef}
        className={clsx(
          'flex flex-col gap-1.5 max-w-[min(85%,720px)]',
          isUser && 'items-end',
        )}
      >
        <div className={clsx(
          'px-3.5 py-3 rounded-3.5 leading-relaxed break-words',
          isUser
            ? 'bg-[rgba(var(--brand-primary),0.12)] border border-[rgba(var(--brand-primary),0.18)]'
            : isInterrupted
              ? 'bg-surface-2 border border-[rgba(var(--semi-orange-5),0.45)]'
              : 'bg-surface-2 border border-default',
        )}
        >
          {isUser
            ? message.content
            : isInterrupted
              ? (
                  <div className="flex flex-col gap-2">
                    {priorSegments.length > 0
                      ? (
                          <AssistantContent
                            content=""
                            thinking={message.thinking}
                            toolCalls={message.tool_calls}
                            segments={priorSegments}
                            streaming={streaming}
                          />
                        )
                      : null}
                    <HumanInterruptCard question={interruptQuestion} />
                  </div>
                )
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
        {!isUser && (message.content || isInterrupted)
          ? (
              <div className="flex gap-2">
                <Button
                  theme="borderless"
                  type="tertiary"
                  size="small"
                  icon={(
                    <span
                      className={clsx(
                        'w-[14px] h-[14px]',
                        isCopied ? 'i-lucide-check text-[var(--semi-color-success)]' : 'i-lucide-copy',
                      )}
                      aria-hidden="true"
                    />
                  )}
                  onClick={() => void handleCopy()}
                >
                  {isCopied ? '已复制' : '复制'}
                </Button>
              </div>
            )
          : null}
      </div>
    </div>
  )
}
