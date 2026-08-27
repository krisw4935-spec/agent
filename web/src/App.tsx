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
    <Layout className="app-shell h-screen h-dvh overflow-hidden bg-surface">
      <Sider className="w-280px shrink-0 bg-surface border-r border-default">
        <Sidebar />
      </Sider>
      <Content className="chat-main flex flex-col h-full min-w-0 bg-surface">
        <ChatPanel />
      </Content>
      <ImageModal />
      <AuthModal />
    </Layout>
  )
}
