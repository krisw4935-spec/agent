import { useCallback, useState } from 'react'
import {
  Banner,
  Button,
  Empty,
  Spin,
  TextArea,
  Typography,
} from '@douyinfe/semi-ui-19'
import clsx from 'clsx'
import { useAuthStore } from '@/store/auth-store'
import { useChatStore } from '@/store/chat-store'
import { MessageFeed } from '@/components/MessageFeed'

const { Title, Text } = Typography

export function ChatPanel() {
  const booting = useAuthStore(state => state.booting)
  const bootError = useAuthStore(state => state.bootError)
  const sessionTitle = useAuthStore(state => state.sessionTitle)
  const busy = useChatStore(state => state.busy)
  const chatError = useChatStore(state => state.chatError)
  const awaitingHuman = useChatStore(state => state.awaitingHuman)
  const sendMessage = useChatStore(state => state.sendMessage)
  const stopGeneration = useChatStore(state => state.stopGeneration)
  const resumeChat = useChatStore(state => state.resumeChat)
  const messages = useChatStore(state => state.messages)
  const userToken = useAuthStore(state => state.userToken)
  const authModalOpen = useAuthStore(state => state.authModalOpen)
  const setAuthModalOpen = useAuthStore(state => state.setAuthModalOpen)
  const [input, setInput] = useState('')

  const isGuest = !userToken
  const lastMsg = messages.at(-1)

  const handleSubmit = useCallback(() => {
    const value = input.trim()
    if (!value || isGuest)
      return
    void sendMessage(value).then(() => setInput(''))
  }, [input, isGuest, sendMessage])

  if (booting) {
    return (
      <section className="flex flex-col items-center justify-center h-full gap-3">
        <Spin size="large" />
        <Title heading={5} className="!mt-4 !mb-0">正在初始化 Math Teacher...</Title>
        <Text type="tertiary">连接知识图谱、向量记忆与 E2B 代码沙箱</Text>
        {bootError ? <Banner type="danger" description={bootError} closeIcon={null} className="!mt-4 max-w-480px" /> : null}
      </section>
    )
  }

  return (
    <>
      {!(isGuest && authModalOpen)
        ? (
          <header className="flex-between gap-4 px-6 py-4 border-b border-default bg-surface">
            <div className="min-w-0">
              <Title heading={5} className="!m-0">{sessionTitle}</Title>
              <Text type="tertiary" size="small">
                支持 LaTeX 公式、Python 代码求解、以及自动函数绘图
              </Text>
            </div>
          </header>
        )
        : null}

      {isGuest
        ? authModalOpen
          ? null
          : (
            <section className="flex-1 min-h-0 flex items-start justify-center pt-10 px-6 pb-6 bg-surface [&_.semi-empty]:m-0 [&_.semi-empty]:p-0 [&_.semi-empty-content]:mt-3">
              <Empty
                image={<span className="i-lucide-user w-[64px] h-[64px] text-brand" aria-hidden="true" />}
                title="登录后开始数学辅导"
                description="登录后可保存历史会话、同步学习记录，并使用完整 Agent 能力。"
              >
                <Button
                  theme="solid"
                  type="primary"
                  size="large"
                  onClick={() => setAuthModalOpen(true)}
                >
                  立即登录
                </Button>
              </Empty>
            </section>
          )
        : (
          <MessageFeed />
        )}

      {!isGuest || !authModalOpen
        ? (
          <div className={clsx(
            'px-6 pt-4 pb-6 border-t border-default bg-surface',
            isGuest && 'opacity-72 pointer-events-none',
          )}
          >
            <div className="max-w-860px mx-auto">
              {awaitingHuman && !isGuest
                ? (
                  <Banner
                    type="warning"
                    closeIcon={null}
                    description="当前流程等待你的确认回复，请在下方输入框直接回答上方问题。"
                    className="!mb-3"
                  />
                )
                : null}

              {lastMsg?.manual_interrupted && !busy && !isGuest
                ? (
                  <Banner
                    type="info"
                    closeIcon={null}
                    description={(
                      <div className="flex items-center justify-between gap-2">
                        <span>上一条回答已手动中断，你可以直接在下方输入新问题，或一键恢复生成。</span>
                        <Button
                          theme="solid"
                          type="warning"
                          size="small"
                          icon={<span className="i-lucide-play w-[14px] h-[14px]" aria-hidden="true" />}
                          onClick={() => void resumeChat()}
                        >
                          恢复生成
                        </Button>
                      </div>
                    )}
                    className="!mb-3"
                  />
                )
                : null}

              <div className="composer-row flex gap-3 items-end">
                <TextArea
                  value={input}
                  onChange={setInput}
                  autosize={{ minRows: 2, maxRows: 6 }}
                  placeholder={
                    isGuest
                      ? '请先登录后再输入数学问题...'
                      : awaitingHuman
                        ? '回复上方确认问题…'
                        : lastMsg?.manual_interrupted
                          ? '输入补充内容继续对话，或点击上方恢复生成...'
                          : '输入数学问题（如：讲解三角函数并画出图像、求导、解方程）...'
                  }
                  maxCount={3000}
                  maxLength={3000}
                  disabled={busy || isGuest}
                  onEnterPress={(event) => {
                    if (!event.shiftKey) {
                      event.preventDefault?.()
                      handleSubmit()
                    }
                  }}
                />
                {busy
                  ? (
                    <Button
                      theme="solid"
                      type="danger"
                      icon={<span className="i-lucide-square w-[14px] h-[14px]" aria-hidden="true" />}
                      onClick={() => void stopGeneration()}
                      aria-label="停止生成"
                    >
                      中断
                    </Button>
                  )
                  : (
                    <Button
                      theme="solid"
                      type="primary"
                      icon={<span className="i-lucide-send w-[16px] h-[16px]" aria-hidden="true" />}
                      disabled={isGuest || !input.trim()}
                      onClick={handleSubmit}
                      aria-label="发送消息"
                    >
                      {awaitingHuman ? '确认回复' : '发送'}
                    </Button>
                  )}
              </div>

              {chatError
                ? (
                  <Banner
                    type="danger"
                    closeIcon={null}
                    description={(
                      <span>
                        {chatError}
                        {isGuest
                          ? (
                            <>
                              {' '}
                              <Button theme="borderless" type="primary" onClick={() => setAuthModalOpen(true)} className="!p-0 !h-auto">
                                去登录
                              </Button>
                            </>
                          )
                          : null}
                      </span>
                    )}
                    className="!mt-3"
                  />
                )
                : null}

              {isGuest && !authModalOpen
                ? (
                  <Text type="tertiary" size="small" className="block mt-3">
                    登录后即可输入数学问题并开始对话。
                  </Text>
                )
                : null}
            </div>
          </div>
        )
        : null}
    </>
  )
}
