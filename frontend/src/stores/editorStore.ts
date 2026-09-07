import { create } from 'zustand';
import type { EditorView } from '@codemirror/view';

export type SaveState = 'saved' | 'saving' | 'dirty' | 'error' | 'conflict';
export type EditorMode = 'edit' | 'preview';

interface EditorState {
  // 현재 컨텍스트
  projectId: number | null;
  chapterId: number | null;
  setContext: (projectId: number | null, chapterId: number | null) => void;

  // CodeMirror 6 View 핸들 — 본문 텍스트 자체는 서버/TanStack Query가 진실
  view: EditorView | null;
  setView: (v: EditorView | null) => void;

  // 자동 저장 상태 (FR-106)
  saveState: SaveState;
  lastSavedAt: number | null;
  setSaveState: (s: SaveState) => void;
  markSaved: () => void;

  // 모드 (편집/미리보기 탭)
  mode: EditorMode;
  setMode: (m: EditorMode) => void;

  // 회차 트리 펼침 상태
  expandedVolumes: Set<number>;
  toggleVolume: (v: number) => void;

  // 글자 수 캐시 (FR-104)
  wordCount: { total: number; noSpace: number; novelpia: number };
  setWordCount: (w: { total: number; noSpace: number; novelpia: number }) => void;

  reset: () => void;
}

export const useEditorStore = create<EditorState>((set, get) => ({
  projectId: null,
  chapterId: null,
  setContext: (projectId, chapterId) => {
    // 작품/회차 전환 시 표시 상태만 초기화한다. 실제 draft/save queue는 회차별 coordinator가 소유한다.
    const prev = get();
    if (projectId !== prev.projectId || chapterId !== prev.chapterId) {
      set({ projectId, chapterId, saveState: 'saved', wordCount: { total: 0, noSpace: 0, novelpia: 0 } });
    } else {
      set({ projectId });
    }
  },

  view: null,
  setView: (v) => set({ view: v }),

  saveState: 'saved',
  lastSavedAt: null,
  setSaveState: (s) => set({ saveState: s }),
  markSaved: () => set({ saveState: 'saved', lastSavedAt: Date.now() }),

  mode: 'edit',
  setMode: (m) => set({ mode: m }),

  expandedVolumes: new Set([1]),
  toggleVolume: (v) => {
    const prev = get().expandedVolumes;
    const next = new Set(prev);
    if (next.has(v)) next.delete(v); else next.add(v);
    set({ expandedVolumes: next });
  },

  wordCount: { total: 0, noSpace: 0, novelpia: 0 },
  setWordCount: (w) => set({ wordCount: w }),

  reset: () =>
    set({
      projectId: null,
      chapterId: null,
      view: null,
      saveState: 'saved',
      lastSavedAt: null,
      mode: 'edit',
      wordCount: { total: 0, noSpace: 0, novelpia: 0 },
    }),
}));
