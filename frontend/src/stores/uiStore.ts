import { create } from 'zustand';

export type Theme = 'dark' | 'light';
export type RightPanelTab = 'ai' | 'refine' | null;

interface UiState {
  /** 다크 기본 + 라이트 토글 (설계서 §1.3 ThemeProvider 역할) */
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;

  /** 우측 패널(S5 AI / S6 윤문) 탭 — 단일 Sheet 인스턴스 */
  rightPanelTab: RightPanelTab;
  setRightPanelTab: (t: RightPanelTab) => void;
}

const THEME_KEY = 'jippeel-theme';

function loadTheme(): Theme {
  try {
    const t = localStorage.getItem(THEME_KEY);
    if (t === 'light' || t === 'dark') return t;
  } catch { /* localStorage 불가 환경 */ }
  return 'dark'; // 다크 기본
}

function applyTheme(t: Theme) {
  const el = document.documentElement;
  el.classList.toggle('light', t === 'light');
  el.classList.toggle('dark', t === 'dark');
}

export const useUiStore = create<UiState>((set, get) => ({
  theme: loadTheme(),
  setTheme: (t) => {
    applyTheme(t);
    try { localStorage.setItem(THEME_KEY, t); } catch { /* noop */ }
    set({ theme: t });
  },
  toggleTheme: () => get().setTheme(get().theme === 'dark' ? 'light' : 'dark'),
  rightPanelTab: null,
  setRightPanelTab: (t) => set({ rightPanelTab: t }),
}));

/** 앱 시작 시 저장된 테마를 DOM에 반영 */
export function initTheme() {
  applyTheme(useUiStore.getState().theme);
}
