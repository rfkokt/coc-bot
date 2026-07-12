import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    proxy: {
      '/state': 'http://localhost:5050',
      '/log': 'http://localhost:5050',
      '/action': 'http://localhost:5050',
      '/save': 'http://localhost:5050',
      '/api/analyze': 'http://localhost:5050',
      '/backend': {
        target: 'http://localhost:5050',
        rewrite: () => '/'
      }
    }
  }
})
