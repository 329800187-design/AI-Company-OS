import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// 后端所有路由前缀
const backendRoutes = [
  '/admin', '/agent-console', '/agents', '/ai', '/auth', '/boss', '/brain',
  '/capabilities', '/commander', '/commanders', '/config', '/cron', '/cto',
  '/data', '/export', '/image', '/marketplace', '/marketing', '/memory',
  '/payment', '/pipeline', '/plugins', '/search', '/skills', '/swarm',
  '/system', '/tasks', '/templates', '/usage', '/user', '/workflows',
  '/integrations',
]

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      ...Object.fromEntries(
        backendRoutes.map(route => [route, 'http://localhost:8000'])
      ),
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
