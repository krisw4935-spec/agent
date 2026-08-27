import { Button, Collapse, Spin, Tag, Typography } from '@douyinfe/semi-ui-19'
import { Streamdown } from 'streamdown'
import { HumanInterruptCard } from '@/components/HumanInterruptCard'
import { getFriendlyToolName, getToolInputLabel, getToolOutputLabel } from '@/lib/format'
import { extractThinkingFromContent } from '@/lib/markdown'
import { katexStreamdownComponents } from '@/lib/katex-streamdown'
import { streamdownPlugins } from '@/lib/streamdown'
import { useChatStore } from '@/store/chat-store'
import type { MessageSegment, ToolCall } from '@/types'

const { Text } = Typography

interface AssistantContentProps {
  content?: string
  thinking?: string
  toolCalls?: ToolCall[]
  segments?: MessageSegment[]
  streaming?: boolean
  interrupted?: boolean
  interruptQuestion?: string
  manualInterrupted?: boolean
}

function parseInterruptQuestion(toolArgs?: string, fallback = ''): string {
  if (!toolArgs)
    return fallback || '请确认后续推导步骤：'
  try {
    const parsed = JSON.parse(toolArgs)
    if (parsed && typeof parsed === 'object' && parsed.question)
      return String(parsed.question)
  }
  catch {}
  return toolArgs || fallback || '请确认后续推导步骤：'
}

function InlineSpin() {
  return (
    <span className="inline-spin-wrap">
      <Spin size="small" />
    </span>
  )
}

function StreamingPlaceholder() {
  return (
    <div className="flex items-center gap-2 py-1">
      <InlineSpin />
      <Text type="secondary">正在分析题目意图与解题策略...</Text>
      <Tag size="small" color="blue">分析中</Tag>
    </div>
  )
}

function ThinkingBlock({ content, completed, elapsed }: { content: string, completed: boolean, elapsed?: number }) {
  return (
    <Collapse defaultActiveKey={completed ? [] : ['thinking']} keepDOM className="assistant-collapse !mb-2">
      <Collapse.Panel
        header={(
          <div className="flex items-center gap-2 flex-wrap">
            {!completed ? <InlineSpin /> : null}
            <Text>深度思考与推理过程{elapsed ? ` (${elapsed}s)` : ''}</Text>
            <Tag size="small" color={completed ? 'green' : 'blue'}>
              {completed ? '已完成' : '思考中'}
            </Tag>
          </div>
        )}
        itemKey="thinking"
      >
        <div className="thinking-content">{content}</div>
      </Collapse.Panel>
    </Collapse>
  )
}

function ToolCallBlock({
  toolName,
  toolArgs,
  toolOutput,
  completed,
  stepNumber,
}: {
  toolName?: string
  toolArgs?: string
  toolOutput?: string
  completed: boolean
  stepNumber: number
}) {
  const friendlyName = getFriendlyToolName(toolName)
  const hasDetails = Boolean(toolArgs || toolOutput)
  const panelKey = `tool-${stepNumber}`

  return (
    <Collapse defaultActiveKey={completed ? [] : [panelKey]} keepDOM className="assistant-collapse !mb-2">
      <Collapse.Panel
        header={(
          <div className="flex items-center gap-2 flex-wrap">
            <Tag size="small" color="grey">{`步骤 ${stepNumber}`}</Tag>
            {!completed ? <InlineSpin /> : null}
            <Text>
              {completed ? `已完成 ${friendlyName}` : `正在调用 ${friendlyName}...`}
            </Text>
            <Tag size="small" color={completed ? 'green' : 'blue'}>
              {completed ? (hasDetails ? '查看详情' : '已完成') : '演算中'}
            </Tag>
          </div>
        )}
        itemKey={panelKey}
      >
        {hasDetails
          ? (
            <div className="flex flex-col gap-3">
              {toolArgs
                ? (
                  <div>
                    <Text type="secondary" size="small" strong>{getToolInputLabel(toolName)}</Text>
                    <pre className="tool-output">{toolArgs}</pre>
                  </div>
                )
                : null}
              {toolOutput
                ? (
                  <div>
                    <Text type="secondary" size="small" strong>{getToolOutputLabel(toolName)}</Text>
                    <pre className="tool-output">{toolOutput}</pre>
                  </div>
                )
                : null}
            </div>
          )
          : null}
      </Collapse.Panel>
    </Collapse>
  )
}

function ManualInterruptBanner() {
  const busy = useChatStore(state => state.busy)
  const resumeChat = useChatStore(state => state.resumeChat)
  return (
    <div className="flex items-center justify-between gap-3 p-2.5 rounded-lg bg-[rgba(var(--semi-orange-5),0.08)] border border-[rgba(var(--semi-orange-5),0.3)] my-2">
      <div className="flex items-center gap-2">
        <Tag size="small" color="orange">⚠️ 已手动中断</Tag>
        <Text type="secondary" size="small">回答已暂停输出</Text>
      </div>
      <Button
        theme="solid"
        type="warning"
        size="small"
        icon={<span className="i-lucide-play w-[14px] h-[14px]" aria-hidden="true" />}
        onClick={() => void resumeChat()}
        disabled={busy}
      >
        继续生成
      </Button>
    </div>
  )
}

function TextBlock({ content, streaming = false }: { content: string, streaming?: boolean }) {
  return (
    <Streamdown
      className="markdown-body"
      plugins={streamdownPlugins}
      components={katexStreamdownComponents}
      isAnimating={streaming}
      mode={streaming ? 'streaming' : 'static'}
    >
      {content}
    </Streamdown>
  )
}

export function AssistantContent({
  content = '',
  thinking = '',
  toolCalls = [],
  segments = [],
  streaming = false,
  interrupted = false,
  interruptQuestion = '',
  manualInterrupted = false,
}: AssistantContentProps) {
  if (streaming && !content && !thinking && segments.length === 0 && !interrupted)
    return <StreamingPlaceholder />

  if (segments.length > 0) {
    let toolCount = 0
    const hasInterruptSegment = segments.some(s => s.tool_name === 'ask_human' && !s.tool_output)

    return (
      <div className="flex flex-col gap-2">
        {segments.map((segment, index) => {
          if (segment.type === 'thinking' && segment.content) {
            return (
              <ThinkingBlock
                key={`thinking-${index}`}
                content={segment.content}
                completed={!streaming || index < segments.length - 1}
              />
            )
          }

          if (segment.type === 'tool_call') {
            if (segment.tool_name === 'ask_human') {
              const q = parseInterruptQuestion(segment.tool_args, segment.status)
              const hasOutput = Boolean(segment.tool_output)
              return (
                <HumanInterruptCard
                  key={`interrupt-${index}`}
                  question={q}
                  answer={segment.tool_output}
                  completed={hasOutput}
                />
              )
            }

            toolCount += 1
            return (
              <ToolCallBlock
                key={`tool-${index}`}
                toolName={segment.tool_name}
                toolArgs={segment.tool_args}
                toolOutput={segment.tool_output}
                completed={!streaming || index < segments.length - 1}
                stepNumber={toolCount}
              />
            )
          }

          if (segment.type === 'text' && segment.content) {
            return (
              <TextBlock
                key={`text-${index}`}
                content={segment.content}
                streaming={streaming && index === segments.length - 1}
              />
            )
          }

          return null
        })}

        {manualInterrupted ? <ManualInterruptBanner /> : null}

        {interrupted && !manualInterrupted && !hasInterruptSegment
          ? (
            <HumanInterruptCard
              key="pending-interrupt"
              question={interruptQuestion || '请确认后续推导步骤：'}
              completed={false}
            />
          )
          : null}
      </div>
    )
  }

  const extracted = extractThinkingFromContent(content)
  const cleanThinking = thinking || extracted.thinking
  const cleanContent = extracted.content || content

  return (
    <div className="flex flex-col gap-2">
      {cleanThinking
        ? <ThinkingBlock content={cleanThinking} completed={!streaming} />
        : null}
      {toolCalls.map((toolCall, index) => {
        if (toolCall.tool_name === 'ask_human') {
          return (
            <HumanInterruptCard
              key={`legacy-interrupt-${index}`}
              question={parseInterruptQuestion(toolCall.tool_args, toolCall.status)}
              answer={toolCall.tool_output}
              completed={Boolean(toolCall.tool_output)}
            />
          )
        }
        return (
          <ToolCallBlock
            key={`legacy-tool-${index}`}
            toolName={toolCall.tool_name}
            toolArgs={toolCall.tool_args}
            toolOutput={toolCall.tool_output}
            completed={!streaming}
            stepNumber={index + 1}
          />
        )
      })}
      {cleanContent ? <TextBlock content={cleanContent} streaming={streaming} /> : null}
      {manualInterrupted ? <ManualInterruptBanner /> : null}
      {interrupted && !manualInterrupted
        ? (
          <HumanInterruptCard
            question={interruptQuestion || '请确认后续推导步骤：'}
            completed={false}
          />
        )
        : null}
      {!cleanContent && !cleanThinking && toolCalls.length === 0 && !interrupted && streaming
        ? <StreamingPlaceholder />
        : null}
    </div>
  )
}
