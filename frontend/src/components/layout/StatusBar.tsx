import { useLocation } from 'react-router-dom';
import { useEditorStore } from '@/stores/editorStore';
import { useAiPanelStore } from '@/stores/aiPanelStore';

/** StatusBar 32px — 회차·글자 수·저장 상태·AI 상태. 원고 작성 화면에서만 표시한다. */
export function StatusBar() {
  const { pathname } = useLocation();
  const chapterId = useEditorStore((s) => s.chapterId);
  const wordCount = useEditorStore((s) => s.wordCount);
  const saveState = useEditorStore((s) => s.saveState);
  const aiStatus = useAiPanelStore((s) => s.status);

  // 회차/글자수/저장 컨텍스트는 집필 화면에만 의미가 있다 — 홈·설정 등에서는 숨긴다.
  // (훅은 조건 없이 항상 호출 — Rules of Hooks)
  if (!/^\/projects\/\d+\/write/.test(pathname)) return null;

  const saveLabel =
    saveState === 'saved' ? '저장됨' : saveState === 'saving' ? '저장 중…' : saveState === 'error' ? '저장 실패' : '변경됨';

  return (
    <footer className="flex h-8 shrink-0 items-center gap-4 border-t border-border bg-card px-4 text-xs text-muted-foreground">
      <span>회차: {chapterId ?? '—'}</span>
      <span className="font-mono tabular-nums">
        글자 {wordCount.total.toLocaleString()} · 공백제외 {wordCount.noSpace.toLocaleString()}
      </span>
      <span aria-live="polite">{saveLabel}</span>
      <span className="ml-auto">AI: {aiStatus.toUpperCase()}</span>
    </footer>
  );
}
