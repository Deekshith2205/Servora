import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Serve index.html for all routes so /app refreshes work in dev.
    historyApiFallback: true,
  },
})
