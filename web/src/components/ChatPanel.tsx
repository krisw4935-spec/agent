import { useCallback, useState } from 'react'
import {
  Banner,
  Button,
  Empty,
  Spin,
  Tag,
  TextArea,
  Typography,
} from '@douyinfe/semi-ui-19'
import { IconSend, IconUser } from '@douyinfe/semi-icons'
import { QUICK_PROMPTS } from '@/lib/format'
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
  const sendMessage = useChatStore(state => state.sendMessage)
  const userToken = useAuthStore(state => state.userToken)
  const authModalOpen = useAuthStore(state => state.authModalOpen)
  const setAuthModalOpen = useAuthStore(state => state.setAuthModalOpen)
  const [input, setInput] = useState('')

  const isGuest = !userToken

  const handleSubmit = useCallback(() => {
    const value = input.trim()
    if (!value || isGuest)
      return
    void sendMessage(value).then(() => setInput(''))
  }, [input, isGuest, sendMessage])

  if (booting) {
    return (
      <section className="boot-panel">
        <Spin size="large" />
        <Title heading={4} style={{ marginTop: 16, marginBottom: 0 }}>正在初始化 Math Teacher...</Title>
        <Text type="tertiary">连接知识图谱、向量记忆与 E2B 代码沙箱</Text>
        {bootError ? <Banner type="danger" description={bootError} closeIcon={null} style={{ marginTop: 16, maxWidth: 480 }} /> : null}
      </section>
    )
  }

  return (
    <>
      {!(isGuest && authModalOpen)
        ? (
            <header className="chat-header">
              <div className="chat-header-main">
                <Title heading={4} style={{ margin: 0 }}>{sessionTitle}</Title>
                <Text type="tertiary" size="small">
                  支持 LaTeX 公式、Python 代码求解、以及自动函数绘图
                </Text>
              </div>
              <Tag color="green" type="light" size="large">Agent 就绪</Tag>
            </header>
          )
        : null}

      {isGuest
        ? authModalOpen
          ? null
          : (
              <section className="auth-gate-panel">
                <Empty
                  image={<IconUser size="extra-large" style={{ color: 'rgb(var(--brand-primary))' }} />}
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
            <div className={`composer-area ${isGuest ? 'is-disabled' : ''}`}>
        <div className="composer-inner">
          <div className="prompt-row">
            {QUICK_PROMPTS.map(item => (
              <Tag
                key={item.label}
                color="green"
                type="ghost"
                size="large"
                style={{ cursor: isGuest || busy ? 'not-allowed' : 'pointer', opacity: isGuest || busy ? 0.55 : 1 }}
                onClick={() => {
                  if (isGuest) {
                    setAuthModalOpen(true)
                    return
                  }
                  if (!busy)
                    void sendMessage(item.prompt)
                }}
              >
                {item.label}
              </Tag>
            ))}
          </div>

          <div className="composer-row">
            <TextArea
              value={input}
              onChange={setInput}
              autosize={{ minRows: 2, maxRows: 6 }}
              placeholder={isGuest ? '请先登录后再输入数学问题...' : '输入数学问题（如：讲解三角函数并画出图像、求导、解方程）...'}
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
            <Button
              theme="solid"
              type="primary"
              icon={<IconSend />}
              loading={busy}
              disabled={busy || isGuest || !input.trim()}
              onClick={handleSubmit}
              aria-label="发送消息"
            >
              {busy ? '发送中' : '发送'}
            </Button>
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
                              <Button theme="borderless" type="primary" onClick={() => setAuthModalOpen(true)} style={{ padding: 0, height: 'auto' }}>
                                去登录
                              </Button>
                            </>
                          )
                        : null}
                    </span>
                  )}
                  style={{ marginTop: 12 }}
                />
              )
            : null}

          {isGuest && !authModalOpen
            ? (
                <Text type="tertiary" size="small" style={{ display: 'block', marginTop: 12 }}>
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
