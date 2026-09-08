import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// Dedicated AI-context browser fixture config.
// Intentionally no backend proxy: every /api/v1/** request must be handled by Playwright.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    host: '127.0.0.1',
    port: 15227,
    strictPort: true,
  },
});
