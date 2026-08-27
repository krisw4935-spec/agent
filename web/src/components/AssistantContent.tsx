import { Collapse, Spin, Tag, Typography } from '@douyinfe/semi-ui-19'
import { Streamdown } from 'streamdown'
import { getFriendlyToolName, getToolInputLabel, getToolOutputLabel } from '@/lib/format'
import { extractThinkingFromContent } from '@/lib/markdown'
import { katexStreamdownComponents } from '@/lib/katex-streamdown'
import { streamdownPlugins } from '@/lib/streamdown'
import type { MessageSegment, ToolCall } from '@/types'

const { Text } = Typography

interface AssistantContentProps {
  content?: string
  thinking?: string
  toolCalls?: ToolCall[]
  segments?: MessageSegment[]
  streaming?: boolean
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
}: AssistantContentProps) {
  if (streaming && !content && !thinking && segments.length === 0)
    return <StreamingPlaceholder />

  if (segments.length > 0) {
    let toolCount = 0
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
      {toolCalls.map((toolCall, index) => (
        <ToolCallBlock
          key={`legacy-tool-${index}`}
          toolName={toolCall.tool_name}
          toolArgs={toolCall.tool_args}
          toolOutput={toolCall.tool_output}
          completed={!streaming}
          stepNumber={index + 1}
        />
      ))}
      {cleanContent ? <TextBlock content={cleanContent} streaming={streaming} /> : null}
      {!cleanContent && !cleanThinking && toolCalls.length === 0 && streaming
        ? <StreamingPlaceholder />
        : null}
    </div>
  )
}
