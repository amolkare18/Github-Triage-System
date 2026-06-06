import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/login': 'http://127.0.0.1:8001',
      '/signup': 'http://127.0.0.1:8001',
      '/logout': 'http://127.0.0.1:8001',
      '/triage': 'http://127.0.0.1:8001',
      '/status': 'http://127.0.0.1:8001',
      '/approve': 'http://127.0.0.1:8001',
      '/generate-comment': 'http://127.0.0.1:8001',
    }
  }
})
