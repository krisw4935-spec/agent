import { Tag, Typography } from '@douyinfe/semi-ui-19'

const { Text, Paragraph } = Typography

interface HumanInterruptCardProps {
  question: string
}

export function HumanInterruptCard({ question }: HumanInterruptCardProps) {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center gap-2 flex-wrap">
        <Tag size="small" color="orange">需要你的确认</Tag>
        <Text type="tertiary" size="small">回复下方问题后继续</Text>
      </div>
      <Paragraph className="!m-0 whitespace-pre-wrap leading-relaxed">
        {question}
      </Paragraph>
      <Text type="tertiary" size="small">
        请在输入框中直接回复，发送后将继续当前辅导流程。
      </Text>
    </div>
  )
}
