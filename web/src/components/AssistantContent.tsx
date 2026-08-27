import { Collapse, Spin, Tag, Typography } from '@douyinfe/semi-ui-19'
import { getFriendlyToolName, getToolInputLabel, getToolOutputLabel } from '@/lib/format'
import { extractThinkingFromContent, parseContent } from '@/lib/markdown'
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
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
      <InlineSpin />
      <Text type="secondary">正在分析题目意图与解题策略...</Text>
      <Tag size="small" color="blue">分析中</Tag>
    </div>
  )
}

function ThinkingBlock({ content, completed, elapsed }: { content: string, completed: boolean, elapsed?: number }) {
  return (
    <Collapse defaultActiveKey={completed ? [] : ['thinking']} keepDOM style={{ marginBottom: 8 }}>
      <Collapse.Panel
        header={(
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
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
    <Collapse defaultActiveKey={completed ? [] : [panelKey]} keepDOM style={{ marginBottom: 8 }}>
      <Collapse.Panel
        header={(
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
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
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
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

function TextBlock({ content }: { content: string }) {
  return (
    <div
      className="markdown-body"
      dangerouslySetInnerHTML={{ __html: parseContent(content) }}
    />
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
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
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

          if (segment.type === 'text' && segment.content)
            return <TextBlock key={`text-${index}`} content={segment.content} />

          return null
        })}
      </div>
    )
  }

  const extracted = extractThinkingFromContent(content)
  const cleanThinking = thinking || extracted.thinking
  const cleanContent = extracted.content || content

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
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
      {cleanContent ? <TextBlock content={cleanContent} /> : null}
      {!cleanContent && !cleanThinking && toolCalls.length === 0 && streaming
        ? <StreamingPlaceholder />
        : null}
    </div>
  )
}
