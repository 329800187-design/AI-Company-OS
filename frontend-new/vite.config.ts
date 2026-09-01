import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// 后端所有路由前缀
const backendRoutes = [
  '/admin', '/agent-console', '/agents', '/ai', '/auth', '/boss', '/brain',
  '/browser-verification',
  '/capabilities', '/config',
  '/data', '/export', '/image', '/marketplace', '/marketing', '/memory',
  '/health', '/minidelivery', '/payment', '/pipeline', '/plugins', '/search', '/skills',
  '/system', '/tasks', '/templates', '/usage', '/user',
  '/integrations',
]

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.VITE_BACKEND_TARGET || env.VITE_API_TARGET || 'http://localhost:8000'
  const wsTarget = backendTarget.replace(/^http/, 'ws')

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      proxy: {
        ...Object.fromEntries(
          backendRoutes.map(route => [route, backendTarget])
        ),
        '/api': backendTarget,
        '/ws': { target: wsTarget, ws: true },
      },
    },
  }
})
