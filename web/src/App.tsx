import { useEffect } from 'react'
import { Layout } from '@douyinfe/semi-ui-19'
import { AuthModal } from '@/components/AuthModal'
import { ChatPanel } from '@/components/ChatPanel'
import { ImageModal } from '@/components/ImageModal'
import { Sidebar } from '@/components/Sidebar'
import { useBoot } from '@/hooks/useBoot'

const { Sider, Content } = Layout

export function App() {
  useBoot()

  useEffect(() => {
    document.title = 'Math Teacher · 智能数学导师'
  }, [])

  return (
    <Layout className="app-shell">
      <Sider
        style={{
          width: 280,
          flexShrink: 0,
          background: 'var(--semi-color-bg-0)',
          borderRight: '1px solid var(--semi-color-border)',
        }}
      >
        <Sidebar />
      </Sider>
      <Content className="chat-main">
        <ChatPanel />
      </Content>
      <ImageModal />
      <AuthModal />
    </Layout>
  )
}
