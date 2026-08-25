import { useEditorStore } from '@/stores/editorStore';
import { useAiPanelStore } from '@/stores/aiPanelStore';

/** §1.1 StatusBar 32px — 현재 회차 · 글자 수(FR-104) · 저장 상태(FR-106) · AI 상태 */
export function StatusBar() {
  const chapterId = useEditorStore((s) => s.chapterId);
  const wordCount = useEditorStore((s) => s.wordCount);
  const saveState = useEditorStore((s) => s.saveState);
  const aiStatus = useAiPanelStore((s) => s.status);

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
