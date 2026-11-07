import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 로컬 화면을 dev 서버 API 에 붙일 때만 쓴다(.env.local, 방법은 .env.example).
  // VITE_ 로 시작하지 않는 값이라 브라우저 번들에 들어가지 않는다.
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.DEV_PROXY_TARGET

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: '127.0.0.1',
      proxy: target
        ? {
            '/api': {
              target,
              changeOrigin: true,
              configure: (proxy) => {
                proxy.on('proxyReq', (proxyReq) => {
                  // dev 서버 API 는 dev 주소에서 온 요청만 받으므로(CORS) 출처를 그 주소로 바꾸고,
                  // 팀 잠금 쿠키를 브라우저 쿠키 뒤에 붙인다.
                  proxyReq.setHeader('origin', target)
                  const cookie = proxyReq.getHeader('cookie')
                  const team = env.DEV_TEAM_COOKIE ? `uxight_team=${env.DEV_TEAM_COOKIE}` : ''
                  proxyReq.setHeader('cookie', [typeof cookie === 'string' ? cookie : '', team].filter(Boolean).join('; '))
                })
              },
            },
          }
        : undefined,
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
  }
})
