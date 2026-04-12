import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const odooTarget = env.VITE_ODOO_URL || 'http://localhost:8069'
  const port = Number(env.VITE_PORT || 5173)

  return {
    plugins: [react()],
    server: {
      host: env.VITE_HOST || '0.0.0.0',
      port,
      proxy: {
        '/ai_core': { target: odooTarget, changeOrigin: true },
        '/purple_invoices': { target: odooTarget, changeOrigin: true },
        '/web': { target: odooTarget, changeOrigin: true },
      },
    },
  }
})
