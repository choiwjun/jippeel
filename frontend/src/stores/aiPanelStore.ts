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
    /** 선택값을 실제 요청에 포함할지 — 패널 체크박스에서 토글 (R-023) */
    includeChapter: boolean;
    includeCharacters: boolean;
    includeLore: boolean;
    /** 본문 키워드와 일치하는 로어 자동 포함 (백로그 P1) */
    autoLore: boolean;
    /** 목차 자동 포함 (G-001) — 현재 회차 시놉시스·다음 회차 방향 */
    autoOutline: boolean;
    /** 미회수 복선 자동 포함 (G-022) */
    autoForeshadow: boolean;
    /** 장면 단위 생성 (G-012) — 선택 장면 본문만 주입 */
    sceneId: number | null;
    /** 작품 문체 프로파일 적용 (G-040) */
    styleProfile: boolean;
  };
  setContext: (c: Partial<AiPanelState['contextSelection']>) => void;

  // 로어 자동 주입 (백로그 P1) — 본문 언급 로어를 백엔드가 선정·주입
  autoLore: boolean;
  setAutoLore: (v: boolean) => void;
  injectedLore: Array<{ id: number; title: string }>;
  setInjectedLore: (items: Array<{ id: number; title: string }>) => void;

  // 주입 투명성 (고도화 G-001/G-022) — start 이벤트에서 수신
  injectedForeshadows: Array<{ id: number; title: string }>;
  setInjectedForeshadows: (items: Array<{ id: number; title: string }>) => void;
  injectedOutline: { current?: boolean; next_title?: string } | null;
  setInjectedOutline: (info: { current?: boolean; next_title?: string } | null) => void;

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

  contextSelection: {
    chapterId: null,
    characterIds: [],
    loreIds: [],
    includeChapter: false,
    includeCharacters: false,
    includeLore: false,
    autoLore: true,
    autoOutline: true,
    autoForeshadow: true,
    sceneId: null,
    styleProfile: false,
  },
  setContext: (c) =>
    set((s) => ({
      contextSelection: {
        ...s.contextSelection,
        ...c,
        // S3/S4 등에서 새 선택을 주입하면 자동 포함 — 패널에서 끈 상태는 유지
        includeChapter: c.chapterId !== undefined && c.chapterId !== null ? true : s.contextSelection.includeChapter,
        includeCharacters: c.characterIds !== undefined && c.characterIds.length > 0 ? true : s.contextSelection.includeCharacters,
        includeLore: c.loreIds !== undefined && c.loreIds.length > 0 ? true : s.contextSelection.includeLore,
      },
    })),

  autoLore: false,
  setAutoLore: (v) => set({ autoLore: v }),
  injectedLore: [],
  setInjectedLore: (items) => set({ injectedLore: items }),

  injectedForeshadows: [],
  setInjectedForeshadows: (items) => set({ injectedForeshadows: items }),
  injectedOutline: null,
  setInjectedOutline: (info) => set({ injectedOutline: info }),

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
  startStream: () => set({ status: 'streaming', streamingText: '', error: null, injectedLore: [], injectedForeshadows: [], injectedOutline: null }),
  appendChunk: (s) => set((st) => ({ streamingText: st.streamingText + s })),
  finishStream: () => set({ status: 'done' }),
  failStream: (e) => set({ status: 'error', error: e }),
  resetResult: () => {
    get().abortStream();
    set({ status: 'idle', streamingText: '', error: null, injectedLore: [], injectedForeshadows: [], injectedOutline: null, pendingGenerate: false });
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
