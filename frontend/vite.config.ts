import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// WSL에서 Vite를 실행하고 Windows venv의 FastAPI를 사용할 때는 localhost가
// 서로 다른 네트워크 네임스페이스를 가리킬 수 있다. dev.sh가 주입하는 주소를
// 우선 사용하고, 일반적인 로컬 실행은 기존 localhost 프록시를 유지한다.
const backendTarget = process.env.JIPPEEL_BACKEND_URL ?? 'http://localhost:8000';

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
        target: backendTarget,
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
