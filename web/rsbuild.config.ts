import path from 'node:path'
import { defineConfig } from '@rsbuild/core'
import { pluginReact } from '@rsbuild/plugin-react'
import { codeInspectorPlugin } from 'code-inspector-plugin'

export default defineConfig({
  plugins: [pluginReact()],
  source: {
    entry: { index: './src/main.tsx' },
    tsconfigPath: './tsconfig.app.json',
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    aliasStrategy: 'prefer-tsconfig',
  },
  html: {
    template: './index.html',
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  output: {
    distPath: {
      root: 'dist',
    },
    cleanDistPath: true,
  },
  tools: {
    rspack: {
      plugins: [
        codeInspectorPlugin({
          bundler: 'rspack',
          showSwitch: true,
          editor: 'cursor',
          launchType: 'open',
        }),
      ],
    },
  },
})
