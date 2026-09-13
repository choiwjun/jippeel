import { create } from "zustand";

export type AiPanelStatus = "idle" | "streaming" | "done" | "error";
export type AiPanelMode = "ai" | "refine";
export type AiGenerationMode = "single" | "parallel";
export type EpisodePurpose = "serial" | "volume_end" | "series_finale";
export type AiContextRequestSource = "editor" | "standalone";

export interface AiContextDirectives {
  episodePurpose: EpisodePurpose;
  approvedForeshadowIds: number[];
  includeRelationships: boolean;
}

export interface AiResultOrigin {
  projectId: number | null;
  chapterId: number | null;
  expectedRevision: number | null;
  includeChapterContent: boolean;
  startedAt: number;
}

export const DEFAULT_DIRECTIVES: AiContextDirectives = {
  episodePurpose: "serial",
  approvedForeshadowIds: [],
  includeRelationships: false,
};

function directiveKey(projectId: number | null, chapterId: number | null) {
  return `${projectId ?? "none"}:${chapterId ?? "none"}`;
}

function makeStartToken(kind: "generate" | "canon") {
  return `${kind}:${Date.now()}:${Math.random().toString(36).slice(2)}`;
}

export interface ParallelProgress {
  phase: "idle" | "planning" | "workers" | "review";
  sceneCount: number;
  started: number;
  completed: number;
  workerLimit: number;
}

/**
 * 회차 브리프 (한국어 회차 품질 슬라이스) — 백엔드 EpisodeBrief와 같은 필드명.
 * 배열 필드는 줄바꿈 구분 원문으로 보관하고, 전송 직전에 배열로 직렬화한다.
 */
export interface EpisodeBriefState {
  emotion_goal: string;
  core_events: string;
  character_choices: string;
  cost: string;
  prohibitions: string;
  next_hook: string;
  ending_intent: string;
  /** '' = 미지정 */
  scene_type: string;
  /** '' = 미지정 */
  target_chars_novelpia: string;
}

export const EMPTY_EPISODE_BRIEF: EpisodeBriefState = {
  emotion_goal: "",
  core_events: "",
  character_choices: "",
  cost: "",
  prohibitions: "",
  next_hook: "",
  ending_intent: "",
  scene_type: "",
  target_chars_novelpia: "",
};

export interface AiPanelState {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;

  mode: AiPanelMode;
  setMode: (m: AiPanelMode) => void;
  generationMode: AiGenerationMode;
  setGenerationMode: (m: AiGenerationMode) => void;
  workerLimit: number;
  setWorkerLimit: (n: number) => void;
  parallelReviewEffort: "" | "low" | "medium" | "high" | "xhigh";
  setParallelReviewEffort: (
    effort: AiPanelState["parallelReviewEffort"],
  ) => void;
  parallelProgress: ParallelProgress;
  setParallelProgress: (p: Partial<ParallelProgress>) => void;

  // 호출 컨텍스트 (설계서 §5.3 / §7.6 — 호출 지점에서 자동 세팅)
  contextSelection: {
    projectId: number | null;
    chapterId: number | null;
    requestSource: AiContextRequestSource;
    characterIds: number[];
    loreIds: number[];
    /** 선택값을 실제 요청에 포함할지 — 패널 체크박스에서 토글 (R-023) */
    includeChapter: boolean;
    includeChapterContent: boolean;
    includeCharacters: boolean;
    includeLore: boolean;
    /** 본문 키워드와 일치하는 로어 자동 포함 (백로그 P1) */
    autoLore: boolean;
    /** 시맨틱 매칭 강화 (G-070) — 2-gram 코사인 하이브리드 랭킹 */
    autoLoreSemantic: boolean;
    /** 목차 자동 포함 (G-001) — 현재 회차 시놉시스·다음 회차 방향 */
    autoOutline: boolean;
    /** 미회수 복선 자동 포함 (G-022) */
    autoForeshadow: boolean;
    /** 장면 단위 생성 (G-012) — 선택 장면 본문만 주입 */
    sceneId: number | null;
    /** 작품 문체 프로파일 적용 (G-040) */
    styleProfile: boolean;
  };
  setContext: (c: Partial<AiPanelState["contextSelection"]>) => void;
  activeEditorIdentity: { projectId: number; chapterId: number } | null;
  setCurrentIdentity: (
    projectId: number | null,
    chapterId: number | null,
  ) => void;
  getDirectives: (
    projectId: number | null,
    chapterId: number | null,
  ) => AiContextDirectives;
  setDirectives: (
    projectId: number | null,
    chapterId: number | null,
    patch: Partial<AiContextDirectives>,
  ) => void;
  resultOrigin: AiResultOrigin | null;
  setResultOrigin: (origin: AiResultOrigin | null) => void;
  reserveAiStart: (kind: "generate" | "canon") => string | null;
  isAiStartCurrent: (token: string) => boolean;
  clearAiStart: (token?: string) => void;
  _pendingAiStart: { kind: "generate" | "canon"; token: string } | null;
  _directiveMap: Record<string, AiContextDirectives>;

  // 로어 자동 주입 (백로그 P1) — 본문 언급 로어를 백엔드가 선정·주입
  autoLore: boolean;
  setAutoLore: (v: boolean) => void;
  injectedLore: Array<{ id: number; title: string }>;
  setInjectedLore: (items: Array<{ id: number; title: string }>) => void;

  // 주입 투명성 (고도화 G-001/G-022) — start 이벤트에서 수신
  injectedForeshadows: Array<{ id: number; title: string }>;
  setInjectedForeshadows: (items: Array<{ id: number; title: string }>) => void;
  injectedOutline: { current?: boolean; next_title?: string } | null;
  setInjectedOutline: (
    info: { current?: boolean; next_title?: string } | null,
  ) => void;

  // 호출 폼 (FR-401/403/407)
  presetId: number | null;
  promptOverride: string;
  maxTokens: number;
  setPreset: (id: number | null) => void;
  setPrompt: (s: string) => void;
  setParams: (p: Partial<Pick<AiPanelState, "maxTokens">>) => void;

  // 회차 브리프 (한국어 회차 품질 슬라이스) — 필수 항목이 모두 채워졌을 때만 context.brief로 전송
  episodeBrief: EpisodeBriefState;
  setEpisodeBrief: (b: Partial<EpisodeBriefState>) => void;

  // 스트리밍 (FR-405) — 누적 텍스트는 메모리에만 존재
  status: AiPanelStatus;
  streamingText: string;
  error: string | null;
  startStream: (origin?: AiResultOrigin) => void;
  appendChunk: (s: string) => void;
  finishStream: () => void;
  failStream: (e: string) => void;
  resetResult: () => void;

  // 감수 패스 — 초안 스트림 완료 후 자동 감수(지적) + 수정본 (같은 SSE 체이닝)
  reviewPass: boolean;
  setReviewPass: (v: boolean) => void;
  /** '' = GPT OAuth provider 기본 강도 사용 */
  reviewEffort: "" | "low" | "medium" | "high" | "xhigh";
  setReviewEffort: (v: AiPanelState["reviewEffort"]) => void;
  reviewInfo: { model: string; provider: string } | null;
  reviewText: string;
  refinedText: string;
  /** 감수 의견 스트림 시작 시 review 탭, 수정본 시작 시 refined 탭으로 자동 전환 */
  resultTab: "draft" | "review" | "refined";
  setReviewInfo: (info: { model: string; provider: string } | null) => void;
  appendReviewChunk: (s: string) => void;
  appendRefinedChunk: (s: string) => void;
  setResultTab: (t: AiPanelState["resultTab"]) => void;

  /**
   * S5 레이스 수정 — 스트림 생명주기를 모듈 스코프(store)에서 관리한다.
   * 뷰 컴포넌트(AiPanel)가 쿼리 settle로 재마운트돼도 스트림은 유지되고,
   * abort는 [중단] 버튼 또는 패널 '의도적 닫힘'(close/toggle-off)에서만 호출된다.
   */
  _abort: (() => void) | null;
  setAbort: (fn: (() => void) | null) => void;
  abortStream: () => void;

  /** provider 준비 중 [생성 시작] 클릭 표식 — settle 후 1회 자동 재시도 */
  pendingGenerate: boolean;
  setPendingGenerate: (v: boolean) => void;
}

export const useAiPanelStore = create<AiPanelState>((set, get) => ({
  isOpen: false,
  open: () => set({ isOpen: true }),
  // 의도적 닫힘 — 진행 중 스트림만 정리한다(데이터 로딩 재마운트와 무관).
  close: () => {
    get().clearAiStart();
    get().abortStream();
    if (get().status === "streaming") get().finishStream();
    set({ isOpen: false, pendingGenerate: false });
  },
  toggle: () => (get().isOpen ? get().close() : get().open()),

  mode: "ai",
  setMode: (m) => set({ mode: m }),
  generationMode: "single",
  setGenerationMode: (m) => set({ generationMode: m }),
  workerLimit: 3,
  setWorkerLimit: (n) => set({ workerLimit: Math.max(2, Math.min(4, n)) }),
  parallelReviewEffort: "xhigh",
  setParallelReviewEffort: (effort) => set({ parallelReviewEffort: effort }),
  parallelProgress: {
    phase: "idle",
    sceneCount: 0,
    started: 0,
    completed: 0,
    workerLimit: 3,
  },
  setParallelProgress: (p) =>
    set((s) => ({ parallelProgress: { ...s.parallelProgress, ...p } })),

  contextSelection: {
    projectId: null,
    chapterId: null,
    requestSource: "standalone",
    characterIds: [],
    loreIds: [],
    includeChapter: false,
    includeChapterContent: false,
    includeCharacters: false,
    includeLore: false,
    autoLore: true,
    autoLoreSemantic: false,
    autoOutline: true,
    autoForeshadow: true,
    sceneId: null,
    styleProfile: false,
  },
  setContext: (c) =>
    set((s) => {
      const explicitStandalone =
        c.projectId !== undefined && c.chapterId === null;
      const nextChapterId =
        c.chapterId !== undefined ? c.chapterId : s.contextSelection.chapterId;
      const nextProjectId =
        c.projectId !== undefined ? c.projectId : s.contextSelection.projectId;
      const chapterIncludedBySelection =
        c.chapterId !== undefined && c.chapterId !== null;
      const chapterExplicitlyCleared = c.chapterId === null;
      const requestSource =
        c.requestSource ??
        (explicitStandalone
          ? "standalone"
          : chapterIncludedBySelection
            ? "editor"
            : s.contextSelection.requestSource);
      return {
        contextSelection: {
          ...s.contextSelection,
          ...c,
          projectId: nextProjectId,
          chapterId: nextChapterId,
          requestSource,
          // S3/S4 등에서 새 선택을 주입하면 자동 포함 — 패널에서 끈 상태는 유지
          includeChapter: chapterExplicitlyCleared
            ? false
            : chapterIncludedBySelection
              ? true
              : s.contextSelection.includeChapter,
          includeChapterContent:
            c.includeChapterContent !== undefined
              ? c.includeChapterContent
              : chapterExplicitlyCleared
                ? false
                : chapterIncludedBySelection
                  ? true
                  : s.contextSelection.includeChapterContent,
          includeCharacters:
            c.characterIds !== undefined
              ? c.characterIds.length > 0
              : s.contextSelection.includeCharacters,
          includeLore:
            c.loreIds !== undefined
              ? c.loreIds.length > 0
              : s.contextSelection.includeLore,
        },
      };
    }),

  activeEditorIdentity: null,
  setCurrentIdentity: (projectId, chapterId) =>
    set((s) => {
      const changed =
        s.contextSelection.projectId !== projectId ||
        s.contextSelection.chapterId !== chapterId;
      const activeEditorIdentity =
        projectId !== null && chapterId !== null
          ? { projectId, chapterId }
          : null;
      const next = {
        ...s.contextSelection,
        projectId,
        chapterId,
        requestSource:
          chapterId !== null ? ("editor" as const) : ("standalone" as const),
        includeChapter:
          chapterId !== null
            ? s.contextSelection.includeChapter || changed
            : false,
        includeChapterContent:
          chapterId !== null
            ? changed
              ? true
              : s.contextSelection.includeChapterContent
            : false,
      };
      return {
        activeEditorIdentity,
        contextSelection: next,
        _pendingAiStart: changed ? null : s._pendingAiStart,
      };
    }),

  getDirectives: (projectId, chapterId) => {
    const found = get()._directiveMap[directiveKey(projectId, chapterId)];
    return found ?? DEFAULT_DIRECTIVES;
  },
  setDirectives: (projectId, chapterId, patch) =>
    set((s) => {
      const key = directiveKey(projectId, chapterId);
      const current = s._directiveMap[key] ?? DEFAULT_DIRECTIVES;
      const next: AiContextDirectives = {
        episodePurpose: patch.episodePurpose ?? current.episodePurpose,
        approvedForeshadowIds:
          patch.approvedForeshadowIds !== undefined
            ? [...patch.approvedForeshadowIds]
            : [...current.approvedForeshadowIds],
        includeRelationships:
          patch.includeRelationships ?? current.includeRelationships,
      };
      return { _directiveMap: { ...s._directiveMap, [key]: next } };
    }),
  resultOrigin: null,
  setResultOrigin: (origin) => set({ resultOrigin: origin }),
  _pendingAiStart: null,
  _directiveMap: {},
  reserveAiStart: (kind) => {
    const pending = get()._pendingAiStart;
    if (pending) return null;
    const token = makeStartToken(kind);
    set({ _pendingAiStart: { kind, token } });
    return token;
  },
  isAiStartCurrent: (token) => get()._pendingAiStart?.token === token,
  clearAiStart: (token) => {
    const pending = get()._pendingAiStart;
    if (!token || pending?.token === token) set({ _pendingAiStart: null });
  },

  autoLore: false,
  setAutoLore: (v) => set({ autoLore: v }),
  injectedLore: [],
  setInjectedLore: (items) => set({ injectedLore: items }),

  injectedForeshadows: [],
  setInjectedForeshadows: (items) => set({ injectedForeshadows: items }),
  injectedOutline: null,
  setInjectedOutline: (info) => set({ injectedOutline: info }),

  presetId: null,
  promptOverride: "",
  maxTokens: 2048,
  setPreset: (id) => set({ presetId: id }),
  setPrompt: (s) => set({ promptOverride: s }),
  setParams: (p) => set(p),

  episodeBrief: { ...EMPTY_EPISODE_BRIEF },
  setEpisodeBrief: (b) =>
    set((s) => ({ episodeBrief: { ...s.episodeBrief, ...b } })),

  status: "idle",
  streamingText: "",
  error: null,
  startStream: (origin) =>
    set({
      status: "streaming",
      streamingText: "",
      error: null,
      injectedLore: [],
      injectedForeshadows: [],
      injectedOutline: null,
      reviewInfo: null,
      reviewText: "",
      refinedText: "",
      resultTab: "draft",
      resultOrigin: origin ?? null,
      parallelProgress: {
        phase: "idle",
        sceneCount: 0,
        started: 0,
        completed: 0,
        workerLimit: get().workerLimit,
      },
    }),
  appendChunk: (s) => set((st) => ({ streamingText: st.streamingText + s })),
  finishStream: () => set({ status: "done" }),
  failStream: (e) => set({ status: "error", error: e }),
  resetResult: () => {
    get().abortStream();
    get().clearAiStart();
    set({
      status: "idle",
      streamingText: "",
      error: null,
      injectedLore: [],
      injectedForeshadows: [],
      injectedOutline: null,
      pendingGenerate: false,
      reviewInfo: null,
      reviewText: "",
      refinedText: "",
      resultTab: "draft",
      resultOrigin: null,
      parallelProgress: {
        phase: "idle",
        sceneCount: 0,
        started: 0,
        completed: 0,
        workerLimit: get().workerLimit,
      },
    });
  },

  reviewPass: false,
  setReviewPass: (v) => set({ reviewPass: v }),
  reviewEffort: "",
  setReviewEffort: (v) => set({ reviewEffort: v }),
  reviewInfo: null,
  reviewText: "",
  refinedText: "",
  resultTab: "draft",
  setReviewInfo: (info) => set({ reviewInfo: info }),
  appendReviewChunk: (s) => set((st) => ({ reviewText: st.reviewText + s })),
  appendRefinedChunk: (s) => set((st) => ({ refinedText: st.refinedText + s })),
  setResultTab: (t) => set({ resultTab: t }),

  _abort: null,
  setAbort: (fn) => set({ _abort: fn }),
  abortStream: () => {
    get().clearAiStart();
    const a = get()._abort;
    if (a) a();
    set({ _abort: null, pendingGenerate: false });
  },

  pendingGenerate: false,
  setPendingGenerate: (v) => set({ pendingGenerate: v }),
}));
