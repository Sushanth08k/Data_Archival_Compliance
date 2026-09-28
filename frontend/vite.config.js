import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/policies': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/audit': 'http://127.0.0.1:8000',
      '/controls': 'http://127.0.0.1:8000',
      '/control-runs': 'http://127.0.0.1:8000',
      '/executions': 'http://127.0.0.1:8000',
      '/approvals': 'http://127.0.0.1:8000',
    },
  },
})

