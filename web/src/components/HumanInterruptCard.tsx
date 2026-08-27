import { useState } from 'react'
import { Button, Input, Tag, Typography } from '@douyinfe/semi-ui-19'
import { useChatStore } from '@/store/chat-store'

const { Text, Paragraph } = Typography

interface HumanInterruptCardProps {
  question: string
  answer?: string
  completed?: boolean
}

export function HumanInterruptCard({ question, answer, completed = false }: HumanInterruptCardProps) {
  const [inlineReply, setInlineReply] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const busy = useChatStore(state => state.busy)

  const handleConfirm = async () => {
    const text = inlineReply.trim()
    if (!text || busy || submitting)
      return
    setSubmitting(true)
    try {
      await useChatStore.getState().sendMessage(text)
    }
    finally {
      setSubmitting(false)
    }
  }

  if (completed || Boolean(answer)) {
    return (
      <div className="flex flex-col gap-2 p-3 rounded-lg bg-[rgba(var(--semi-green-5),0.06)] border border-[rgba(var(--semi-green-5),0.25)] my-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          <Tag size="small" color="green">✅ 已完成决策确认</Tag>
          <Text type="tertiary" size="small">辅导流程已接续</Text>
        </div>
        <Paragraph className="!m-0 text-xs text-[var(--semi-color-text-1)] whitespace-pre-wrap leading-relaxed">
          {question}
        </Paragraph>
        {answer
          ? (
            <div className="text-xs bg-[var(--semi-color-bg-0)] px-2.5 py-1.5 rounded border border-[rgba(var(--semi-green-5),0.3)] text-[var(--semi-color-text-0)] flex items-center gap-1.5">
              <span className="text-[var(--semi-color-success)] font-medium">✓ 你的选择：</span>
              <span>{answer}</span>
            </div>
          )
          : null}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2.5 p-3.5 rounded-lg bg-[rgba(var(--semi-orange-5),0.06)] border border-[rgba(var(--semi-orange-5),0.35)] my-1.5">
      <div className="flex items-center gap-2 flex-wrap">
        <Tag size="small" color="orange">需要你的确认</Tag>
        <Text type="tertiary" size="small">回复后在当前卡片中继续</Text>
      </div>
      <Paragraph className="!m-0 text-sm whitespace-pre-wrap leading-relaxed text-[var(--semi-color-text-0)] font-medium">
        {question}
      </Paragraph>
      <div className="flex gap-2 items-center mt-1">
        <Input
          value={inlineReply}
          onChange={setInlineReply}
          placeholder="在此输入你的选择或补充条件..."
          onEnterPress={() => void handleConfirm()}
          disabled={busy || submitting}
          className="flex-1"
        />
        <Button
          theme="solid"
          type="warning"
          size="small"
          onClick={() => void handleConfirm()}
          loading={submitting || busy}
          disabled={!inlineReply.trim()}
        >
          确认并继续
        </Button>
      </div>
      <Text type="tertiary" size="small" className="text-xs">
        💡 也可在页面底部输入框中直接发送。
      </Text>
    </div>
  )
}
