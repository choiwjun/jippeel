import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// dev 프록시 → FastAPI (/api) — 사양 §2.2
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 벤더 청크 분리 — 단일 번들 비대화 완화 + 배포 캐시 효율
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          editor: ['@codemirror/state', '@codemirror/view', '@codemirror/language', '@codemirror/lang-markdown'],
          markdown: ['markdown-it', 'dompurify', 'diff'],
          data: ['@tanstack/react-query', 'zustand'],
        },
      },
    },
  },
});
