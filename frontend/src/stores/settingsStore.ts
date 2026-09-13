import { create } from 'zustand';

/**
 * 사용자 환경설정 — MVP는 localStorage 영속.
 * 백엔드 GET/PATCH /api/v1/settings 연동은 Sprint 4b(S7)에서 hydrate로 교체.
 */

export type FontFamily = 'pretendard' | 'noto-serif-kr';
export type RefineRoute = 'auto' | 'light' | 'standard' | 'heavy';
/** U04 시니어 확대 모드 — 화면 전체 기준 글자 크기 */
export type UiScale = 'normal' | 'large' | 'xlarge';

interface SettingsState {
  fontFamily: FontFamily;
  lineHeight: number;              // 1.7 ~ 1.9 (§4.2)
  autoSaveIntervalMs: number;      // 500~5000, 기본 1500 (FR-106)
  /** m-7 — CodeMirror lineNumbers, 기본 OFF(집중 모드) + Compartment 토글 */
  lineNumbers: boolean;
  defaultRefineRoute: RefineRoute;
  uiScale: UiScale;

  setFontFamily: (f: FontFamily) => void;
  setLineHeight: (v: number) => void;
  setAutoSaveInterval: (ms: number) => void;
  setLineNumbers: (b: boolean) => void;
  setDefaultRefineRoute: (r: RefineRoute) => void;
  setUiScale: (s: UiScale) => void;
  hydrate: (s: Partial<Omit<SettingsState, keyof Actions>>) => void;
}

type Actions = 'setFontFamily' | 'setLineHeight' | 'setAutoSaveInterval' | 'setLineNumbers' | 'setDefaultRefineRoute' | 'setUiScale' | 'hydrate';

const SETTINGS_KEY = 'jippeel-settings';

function load(): Partial<SettingsState> {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) return JSON.parse(raw) as Partial<SettingsState>;
  } catch { /* noop */ }
  return {};
}

function persist(s: SettingsState) {
  try {
    const { setFontFamily, setLineHeight, setAutoSaveInterval, setLineNumbers, setDefaultRefineRoute, setUiScale, hydrate, ...data } = s;
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(data));
  } catch { /* noop */ }
}

const defaults = {
  fontFamily: 'pretendard' as FontFamily,
  lineHeight: 1.85,
  autoSaveIntervalMs: 1500,
  lineNumbers: false, // m-7: 기본 OFF
  defaultRefineRoute: 'auto' as RefineRoute,
  uiScale: 'normal' as UiScale,
};

/** uiScale → 루트 확대 배율 (index.css의 html[data-ui-scale] 규칙과 에디터 배율 공용) */
export const UI_SCALE_FACTOR: Record<UiScale, number> = {
  normal: 1,
  large: 1.15,
  xlarge: 1.3,
};

export function applyUiScale(s: UiScale) {
  document.documentElement.dataset.uiScale = s;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  ...defaults,
  ...load(),
  setFontFamily: (f) => { set({ fontFamily: f }); persist(get()); },
  setLineHeight: (v) => { set({ lineHeight: v }); persist(get()); },
  setAutoSaveInterval: (ms) => { set({ autoSaveIntervalMs: Math.min(5000, Math.max(500, ms)) }); persist(get()); },
  setLineNumbers: (b) => { set({ lineNumbers: b }); persist(get()); },
  setDefaultRefineRoute: (r) => { set({ defaultRefineRoute: r }); persist(get()); },
  setUiScale: (s) => { set({ uiScale: s }); applyUiScale(s); persist(get()); },
  hydrate: (s) => {
    set(s);
    if (s.uiScale) applyUiScale(s.uiScale);
    persist(get());
  },
}));
