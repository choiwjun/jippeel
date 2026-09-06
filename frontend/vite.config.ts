import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// dev 프록시 → FastAPI (/api) — 사양 §2.2
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  build: {
    rollupOptions: {
      output: {
        // 벤더 청크 분리 — 단일 번들 비대화 완화 + 배포 캐시 효율
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-editor': [
            '@codemirror/state',
            '@codemirror/view',
            '@codemirror/language',
            '@codemirror/lang-markdown',
            'markdown-it',
            'diff',
          ],
          'vendor-data': ['@tanstack/react-query', 'zustand'],
        },
      },
    },
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
