import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
  server: {
    fs: {
      allow: [path.resolve(__dirname, '..')],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: [
      '../tests/frontend/**/*.test.ts',
      '../tests/frontend/**/*.test.tsx',
      '../tests/essential/test_*.ts',
      '../tests/essential/test_*.tsx',
    ],
    server: {
      deps: {
        moduleDirectories: ['node_modules', path.resolve(__dirname, 'node_modules')],
      },
    },
  },
})
