import { useState } from 'react'
import {
  Banner,
  Button,
  Form,
  Modal,
  TabPane,
  Tabs,
  Typography,
} from '@douyinfe/semi-ui-19'
import { useAuthStore } from '@/store/auth-store'
import { useChatStore } from '@/store/chat-store'

const { Text } = Typography

interface LoginFormValues {
  email: string
  password: string
}

interface RegisterFormValues {
  username?: string
  email: string
  password: string
}

export function AuthModal() {
  const open = useAuthStore(state => state.authModalOpen)
  const userToken = useAuthStore(state => state.userToken)
  const authError = useAuthStore(state => state.authError)
  const setAuthModalOpen = useAuthStore(state => state.setAuthModalOpen)
  const setAuthError = useAuthStore(state => state.setAuthError)
  const login = useAuthStore(state => state.login)
  const register = useAuthStore(state => state.register)
  const loadSessions = useAuthStore(state => state.loadSessions)
  const switchSession = useAuthStore(state => state.switchSession)
  const createSession = useAuthStore(state => state.createSession)
  const loadSessionMessages = useChatStore(state => state.loadSessionMessages)

  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [submitting, setSubmitting] = useState(false)
  const isGuest = !userToken

  const handleClose = () => {
    if (isGuest) {
      setAuthError('系统要求必须登录后使用。')
      return
    }
    setAuthModalOpen(false)
  }

  const handleLogin = async (values: LoginFormValues) => {
    setSubmitting(true)
    try {
      await login(values.email.trim(), values.password.trim())
      await loadSessions()
      const auth = useAuthStore.getState()
      if (auth.sessions.length > 0) {
        switchSession(auth.sessions[0])
        await loadSessionMessages()
      }
      else {
        await createSession()
        await loadSessionMessages()
      }
    }
    catch (error) {
      const message = error instanceof Error ? error.message : '登录失败'
      setAuthError(`登录失败: ${message}`)
    }
    finally {
      setSubmitting(false)
    }
  }

  const handleRegister = async (values: RegisterFormValues) => {
    setSubmitting(true)
    try {
      await register(values.email.trim(), values.password.trim(), values.username?.trim() || null)
      await createSession()
      await loadSessionMessages()
    }
    catch (error) {
      const message = error instanceof Error ? error.message : '注册失败'
      setAuthError(`注册失败: ${message}`)
    }
    finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      className="auth-modal"
      modalContentClass=""
      header={null}
      title={null}
      closable={false}
      visible={open}
      onCancel={handleClose}
      footer={null}
      closeOnEsc={!isGuest}
      maskClosable={!isGuest}
      width={480}
      centered
      zIndex={2000}
      maskStyle={{ backgroundColor: isGuest ? 'rgba(15, 23, 42, 0.88)' : 'rgba(15, 23, 42, 0.72)' }}
      bodyStyle={{ paddingBottom: '24px', background: 'var(--semi-color-bg-0)' }}
    >
      <div className="auth-modal-body">
        <Tabs
          type="line"
          activeKey={tab}
          onChange={(key) => {
            setTab(key as 'login' | 'register')
            setAuthError(null)
          }}
        >
          <TabPane tab="用户登录" itemKey="login">
            {authError && tab === 'login'
              ? <Banner type="danger" description={authError} closeIcon={null} style={{ marginBottom: 16 }} />
              : null}
            <Form
              initValues={{ email: 'student@math-teacher.local', password: 'Math123456!' }}
              onSubmit={(values) => void handleLogin(values as LoginFormValues)}
            >
              <Text type="tertiary" size="small" style={{ display: 'block', marginBottom: 16 }}>
                默认体验账号已预填，可直接登录。
              </Text>
              <Form.Input
                field="email"
                label="用户名 / 邮箱"
                type="email"
                rules={[{ required: true, message: '请输入邮箱' }]}
                showClear
              />
              <Form.Input
                field="password"
                label="密码"
                mode="password"
                rules={[{ required: true, message: '请输入密码' }]}
                showClear
              />
              <Button
                htmlType="submit"
                type="primary"
                theme="solid"
                block
                loading={submitting}
                style={{ marginTop: 8 }}
              >
                登录辅导室
              </Button>
            </Form>
          </TabPane>
          <TabPane tab="新用户注册" itemKey="register">
            {authError && tab === 'register'
              ? <Banner type="danger" description={authError} closeIcon={null} style={{ marginBottom: 16 }} />
              : null}
            <Form onSubmit={(values) => void handleRegister(values as RegisterFormValues)}>
              <Form.Input field="username" label="昵称（可选）" maxLength={50} showClear />
              <Form.Input
                field="email"
                label="邮箱地址"
                type="email"
                rules={[{ required: true, message: '请输入邮箱' }]}
                showClear
              />
              <Form.Input
                field="password"
                label="密码"
                mode="password"
                rules={[
                  { required: true, message: '请输入密码' },
                  { min: 8, message: '密码至少 8 位' },
                ]}
                showClear
              />
              <Text type="tertiary" size="small" style={{ display: 'block', marginBottom: 16 }}>
                密码至少 8 位，需包含大小写字母、数字和符号。
              </Text>
              <Button htmlType="submit" type="primary" theme="solid" block loading={submitting}>
                注册账号
              </Button>
            </Form>
          </TabPane>
        </Tabs>
      </div>
    </Modal>
  )
}
