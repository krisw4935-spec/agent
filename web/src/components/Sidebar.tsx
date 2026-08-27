import { useCallback, useMemo } from 'react'
import {
  Avatar,
  Badge,
  Button,
  List,
  Popconfirm,
  Tag,
  Typography,
} from '@douyinfe/semi-ui-19'
import { IconBookStroked, IconDeleteStroked, IconExit, IconLock, IconPlus, IconComment } from '@douyinfe/semi-icons'
import { fetchMessages } from '@/api/chatbot'
import { formatRelativeTime } from '@/lib/format'
import { useAuthStore } from '@/store/auth-store'
import { useChatStore } from '@/store/chat-store'

const { Text, Title, Paragraph } = Typography

export function Sidebar() {
  const user = useAuthStore(state => state.user)
  const userToken = useAuthStore(state => state.userToken)
  const sessionId = useAuthStore(state => state.sessionId)
  const sessions = useAuthStore(state => state.sessions)
  const sessionMeta = useMemo(() => {
    const prefix = user ? `用户: ${user.username || user.email}` : '游客会话'
    const sid = sessionId ? `\nID: ${sessionId.slice(0, 8)}...` : ''
    return `${prefix}${sid}`
  }, [sessionId, user])

  const setAuthModalOpen = useAuthStore(state => state.setAuthModalOpen)
  const logout = useAuthStore(state => state.logout)
  const switchSession = useAuthStore(state => state.switchSession)
  const deleteSession = useAuthStore(state => state.deleteSession)
  const startNewSession = useChatStore(state => state.startNewSession)
  const setMessages = useChatStore(state => state.setMessages)
  const setChatError = useChatStore(state => state.setChatError)

  const handleSwitchSession = useCallback(async (sessionIdToSwitch: string, token?: string, name?: string | null) => {
    const session = sessions.find(item => item.session_id === sessionIdToSwitch)
    if (!session)
      return

    switchSession({
      ...session,
      token: token ? { access_token: token } : session.token,
      name: name ?? session.name,
    })
    setChatError(null)

    const auth = useAuthStore.getState()
    const sessionToken = token || auth.sessionToken
    if (!sessionToken) {
      setMessages([])
      return
    }

    try {
      const data = await fetchMessages(sessionToken)
      const msgs = data.messages || []
      setMessages(msgs.length ? msgs : [{ role: 'assistant', content: '你好！我是 **Math Teacher** 数学导师。' }])
    }
    catch (error) {
      const message = error instanceof Error ? error.message : '加载失败'
      setMessages([{ role: 'assistant', content: `⚠️ 加载历史记录失败: ${message}` }])
    }
  }, [sessions, setChatError, setMessages, switchSession])

  const handleDeleteSession = useCallback(async (targetSessionId: string) => {
    await deleteSession(targetSessionId)
    await useChatStore.getState().loadSessionMessages()
  }, [deleteSession])

  return (
    <div className="sidebar-inner" aria-label="会话侧栏">
      <div>
        <div className="sidebar-brand">
          <Avatar color="green" size="default" shape="square">
            <IconBookStroked />
          </Avatar>
          <div>
            <Title heading={5} style={{ margin: 0 }}>Math Teacher</Title>
            <Tag color="green" size="small" style={{ marginTop: 4 }}>v2.0 · 图文智能体</Tag>
          </div>
        </div>
        <Paragraph type="tertiary" size="small" style={{ marginTop: 12, marginBottom: 0 }}>
          数形结合 · 步骤批改 · E2B 代码自验 · 质检审校
        </Paragraph>
      </div>

      <div className="sidebar-user-card">
        {!userToken || !user
          ? (
            <div className="sidebar-user-row">
              <div className="sidebar-user-meta">
                <Avatar color="grey" size="small">
                  <IconLock />
                </Avatar>
                <Text type="secondary">请先登录</Text>
              </div>
              <Button theme="solid" type="primary" size="small" onClick={() => setAuthModalOpen(true)}>
                登录
              </Button>
            </div>
          )
          : (
            <div className="sidebar-user-row">
              <div className="sidebar-user-meta">
                <Avatar color="green" size="small">
                  {(user.username || user.email || '用')[0]?.toUpperCase()}
                </Avatar>
                <div style={{ minWidth: 0 }}>
                  <Text strong ellipsis={{ showTooltip: true }}>{user.username || user.email.split('@')[0]}</Text>
                  <br />
                  <Text type="tertiary" size="small" ellipsis={{ showTooltip: true }}>{user.email}</Text>
                </div>
              </div>
              <Popconfirm
                title="确定要退出登录吗？"
                onConfirm={() => {
                  logout()
                  useChatStore.getState().setMessages([{
                    role: 'assistant',
                    content: '您已退出登录。请重新登录以开启辅导对话与查看历史记录。',
                  }])
                }}
              >
                <Button theme="borderless" type="tertiary" icon={<IconExit />} aria-label="退出登录" />
              </Popconfirm>
            </div>
          )}
      </div>

      <Button
        theme="solid"
        type="primary"
        block
        icon={<IconPlus />}
        onClick={() => void startNewSession()}
      >
        开启新会话
      </Button>

      <div className="session-list-wrap">
        <div className="session-list-header">
          <Text strong>历史会话</Text>
          <Badge count={sessions.length} type="primary" />
        </div>
        <div className="session-scroll" role="listbox" aria-label="历史会话列表">
          {sessions.length === 0
            ? (
              <Text type="tertiary" size="small">
                {userToken ? '暂无历史会话' : '登录后可保存多个历史会话'}
              </Text>
            )
            : (
              <List
                dataSource={sessions}
                split={false}
                renderItem={(session) => {
                  const isActive = session.session_id === sessionId
                  const title = session.name || '新会话'
                  const timeStr = formatRelativeTime(session.created_at)
                  return (
                    <List.Item
                      style={{
                        padding: '10px 12px',
                        borderRadius: 10,
                        marginBottom: 6,
                        cursor: 'pointer',
                        background: isActive ? 'rgba(var(--semi-blue-5), 0.1)' : 'transparent',
                        border: isActive ? '1px solid rgba(var(--semi-blue-5), 0.2)' : '1px solid transparent',
                      }}
                      onClick={() => void handleSwitchSession(
                        session.session_id,
                        session.token?.access_token,
                        session.name,
                      )}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', minWidth: 0 }}>
                        <IconComment style={{ flexShrink: 0, color: 'var(--semi-color-text-2)' }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <Text ellipsis={{ showTooltip: true }}>{title}</Text>
                          {timeStr ? <Text type="tertiary" size="small">{timeStr}</Text> : null}
                        </div>
                        <Popconfirm
                          title="确定要删除此会话记录吗？"
                          onConfirm={() => void handleDeleteSession(session.session_id)}
                        >
                          <Button
                            theme="borderless"
                            type="tertiary"
                            size="small"
                            icon={<IconDeleteStroked />}
                            aria-label="删除会话"
                            onClick={event => event.stopPropagation()}
                          />
                        </Popconfirm>
                      </div>
                    </List.Item>
                  )
                }}
              />
            )}
        </div>
      </div>

      <div className="feature-tags">
        {['E2B 云端代码沙箱', 'Critic 双智能体审校', 'Matplotlib 图像绘制', 'Mem0 长期学情记忆'].map(item => (
          <Tag key={item} color="green" type="ghost" size="small">{item}</Tag>
        ))}
      </div>

      <div className="sidebar-footer">
        <Text type="tertiary" size="small" style={{ whiteSpace: 'pre-wrap', fontFamily: 'ui-monospace, monospace' }}>
          {sessionMeta}
        </Text>
      </div>
    </div>
  )
}
