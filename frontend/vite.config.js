import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    tailwindcss(),
    react()
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: { 
      '/api': { 
        target: process.env.VITE_API_BASE || 'http://backend:8080', 
        changeOrigin: true,
        timeout: 1800000, // 30 minutos
        proxyTimeout: 1800000 // 30 minutos
      } 
    },
    hmr: process.env.VITE_HMR_HOST
      ? { host: process.env.VITE_HMR_HOST, port: 5173 }
      : undefined
  }
})
