import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from '@douyinfe/semi-ui-19'
import { App } from '@/App'
import { semiLocale } from '@/lib/semi-theme'
import 'katex/dist/katex.min.css'
import 'streamdown/styles.css'
import '@/styles/global.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider locale={semiLocale}>
      <App />
    </ConfigProvider>
  </StrictMode>,
)
