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
import clsx from 'clsx'
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
    const sid = sessionId ? `\nSESSION ID: ${sessionId}` : ''
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
    <div className="flex flex-col h-full py-5 px-4 gap-3 overflow-hidden" aria-label="会话侧栏">
      <div>
        <div className="flex gap-3 items-center">
          <Avatar color="green" size="default" shape="square">
            <span className="i-lucide-book w-[16px] h-[16px]" aria-hidden="true" />
          </Avatar>
          <div className="flex flex-col">
            <div className="text-sm font-bold">Math Teacher</div>
            <div className="text-xs text-gray-500">v2.0 · 图文智能体</div>
          </div>
        </div>
      </div>

      <div className="p-3 rounded-3 bg-surface border border-default">
        {!userToken || !user
          ? (
            <div className="flex-between gap-2">
              <div className="flex items-center gap-2.5 min-w-0">
                <Avatar color="grey" size="small" className="shrink-0">
                  <span className="i-lucide-lock w-[14px] h-[14px]" aria-hidden="true" />
                </Avatar>
                <Text type="secondary">请先登录</Text>
              </div>
              <Button theme="solid" type="primary" size="small" onClick={() => setAuthModalOpen(true)}>
                登录
              </Button>
            </div>
          )
          : (
            <div className="flex-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <Avatar color="green" size="small" className="shrink-0">
                  {(user.username || user.email || '用')[0]?.toUpperCase()}
                </Avatar>
                <div className="min-w-0">
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
                <Button theme="borderless" type="tertiary" icon={<span className="i-lucide-log-out w-[16px] h-[16px]" aria-hidden="true" />} aria-label="退出登录" />
              </Popconfirm>
            </div>
          )}
      </div>

      <Button
        theme="solid"
        type="primary"
        block
        icon={<span className="i-lucide-plus w-[16px] h-[16px]" aria-hidden="true" />}
        onClick={() => void startNewSession()}
      >
        开启新会话
      </Button>

      <div className="flex-1 min-h-0 flex flex-col gap-2">
        <div className="flex-between">
          <Text strong>历史会话</Text>
          <Badge count={sessions.length} type="primary" />
        </div>
        <div className="flex-1 overflow-y-auto -mx-1 px-1 [&_.semi-list-item]:transition-[background-color,border-color] [&_.semi-list-item]:duration-150" role="listbox" aria-label="历史会话列表">
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
                      className={clsx(
                        'px-3 py-2.5 rounded-2.5 mb-1.5 cursor-pointer border border-transparent transition-colors duration-150',
                        isActive && 'bg-[rgba(var(--semi-blue-5),0.1)] border-[rgba(var(--semi-blue-5),0.2)]',
                      )}
                      onClick={() => void handleSwitchSession(
                        session.session_id,
                        session.token?.access_token,
                        session.name,
                      )}
                    >
                      <div className="flex items-center gap-2.5 w-full min-w-0">
                        <span className="i-lucide-message-circle w-[16px] h-[16px] shrink-0 text-[var(--semi-color-text-2)]" aria-hidden="true" />
                        <div className="flex-1 min-w-0">
                          <Text ellipsis={{ showTooltip: true }}>{title}</Text>
                          {timeStr ? <Text type="tertiary" className="pl-2" size="small">{timeStr}</Text> : null}
                        </div>
                        <Popconfirm
                          title="确定要删除此会话记录吗？"
                          onConfirm={() => void handleDeleteSession(session.session_id)}
                        >
                          <Button
                            theme="borderless"
                            type="tertiary"
                            size="small"
                            icon={<span className="i-lucide-trash-2 w-[14px] h-[14px]" aria-hidden="true" />}
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

      <div className="pt-3 border-t border-default">
        <Text type="tertiary" size="small" className="whitespace-pre-wrap font-mono w-full block">
          {sessionMeta}
        </Text>
      </div>
    </div >
  )
}
