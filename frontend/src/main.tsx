import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import { initTheme } from '@/stores/uiStore';
import { applyUiScale, useSettingsStore } from '@/stores/settingsStore';

// 다크 기본 + 저장된 라이트/다크 프리퍼런스 반영
initTheme();
// U04 — 저장된 화면 확대 배율 반영
applyUiScale(useSettingsStore.getState().uiScale);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
