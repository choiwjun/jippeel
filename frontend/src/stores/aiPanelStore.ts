import { create } from 'zustand';

export type AiPanelStatus = 'idle' | 'streaming' | 'done' | 'error';
export type AiPanelMode = 'ai' | 'refine';

export interface AiPanelState {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;

  mode: AiPanelMode;
  setMode: (m: AiPanelMode) => void;

  // 호출 컨텍스트 (설계서 §5.3 / §7.6 — 호출 지점에서 자동 세팅)
  contextSelection: {
    chapterId: number | null;
    characterIds: number[];
    loreIds: number[];
  };
  setContext: (c: Partial<AiPanelState['contextSelection']>) => void;

  // 호출 폼 (FR-401/403/407)
  endpointId: number | null;
  presetId: number | null;
  model: string;
  promptOverride: string;
  temperature: number;
  maxTokens: number;
  setEndpoint: (id: number) => void;
  setPreset: (id: number | null) => void;
  setModel: (m: string) => void;
  setPrompt: (s: string) => void;
  setParams: (p: Partial<Pick<AiPanelState, 'temperature' | 'maxTokens'>>) => void;

  // 스트리밍 (FR-405) — 누적 텍스트는 메모리에만 존재
  status: AiPanelStatus;
  streamingText: string;
  error: string | null;
  startStream: () => void;
  appendChunk: (s: string) => void;
  finishStream: () => void;
  failStream: (e: string) => void;
  resetResult: () => void;

  /**
   * S5 레이스 수정 — 스트림 생명주기를 모듈 스코프(store)에서 관리한다.
   * 뷰 컴포넌트(AiPanel)가 쿼리 settle로 재마운트돼도 스트림은 유지되고,
   * abort는 [중단] 버튼 또는 패널 '의도적 닫힘'(close/toggle-off)에서만 호출된다.
   */
  _abort: (() => void) | null;
  setAbort: (fn: (() => void) | null) => void;
  abortStream: () => void;

  /** endpoints 로딩 중 [생성 시작] 클릭 표식 — settle 후 1회 자동 재시도 */
  pendingGenerate: boolean;
  setPendingGenerate: (v: boolean) => void;
}

export const useAiPanelStore = create<AiPanelState>((set, get) => ({
  isOpen: false,
  open: () => set({ isOpen: true }),
  // 의도적 닫힘 — 진행 중 스트림만 정리한다(데이터 로딩 재마운트와 무관).
  close: () => {
    get().abortStream();
    if (get().status === 'streaming') get().finishStream();
    set({ isOpen: false, pendingGenerate: false });
  },
  toggle: () => (get().isOpen ? get().close() : get().open()),

  mode: 'ai',
  setMode: (m) => set({ mode: m }),

  contextSelection: { chapterId: null, characterIds: [], loreIds: [] },
  setContext: (c) => set((s) => ({ contextSelection: { ...s.contextSelection, ...c } })),

  endpointId: null,
  presetId: null,
  model: '',
  promptOverride: '',
  temperature: 0.7,
  maxTokens: 2048,
  setEndpoint: (id) => {
    if (id !== get().endpointId) set({ endpointId: id, model: '' });
    else set({ endpointId: id });
  },
  setPreset: (id) => set({ presetId: id }),
  setModel: (m) => set({ model: m }),
  setPrompt: (s) => set({ promptOverride: s }),
  setParams: (p) => set(p),

  status: 'idle',
  streamingText: '',
  error: null,
  startStream: () => set({ status: 'streaming', streamingText: '', error: null }),
  appendChunk: (s) => set((st) => ({ streamingText: st.streamingText + s })),
  finishStream: () => set({ status: 'done' }),
  failStream: (e) => set({ status: 'error', error: e }),
  resetResult: () => {
    get().abortStream();
    set({ status: 'idle', streamingText: '', error: null, pendingGenerate: false });
  },

  _abort: null,
  setAbort: (fn) => set({ _abort: fn }),
  abortStream: () => {
    const a = get()._abort;
    if (a) a();
    set({ _abort: null, pendingGenerate: false });
  },

  pendingGenerate: false,
  setPendingGenerate: (v) => set({ pendingGenerate: v }),
}));
