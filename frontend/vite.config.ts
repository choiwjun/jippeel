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
        // QA Minor #3 — 청크 크기 경고 해소: vendor 분리
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          editor: ['@codemirror/state', '@codemirror/view', '@codemirror/language', '@codemirror/lang-markdown'],
          markdown: ['markdown-it', 'dompurify', 'diff'],
        },
      },
    },
  },
});
