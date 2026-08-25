import { useEditorStore } from '@/stores/editorStore';

/** FR-104 — 공백제외 글자 수 상시 노출 (노벨피아 PLUS 3,000자 조건 확인용). */
export function WordCountFooter() {
  const wordCount = useEditorStore((s) => s.wordCount);
  const meets3000 = wordCount.noSpace >= 3000;

  return (
    <div className="flex items-center gap-3 border-t border-border bg-card px-4 py-1.5 text-xs text-muted-foreground">
      <span className="font-mono tabular-nums">글자 {wordCount.total.toLocaleString()}</span>
      <span className="font-mono font-bold tabular-nums text-foreground">
        공백제외 {wordCount.noSpace.toLocaleString()}
      </span>
      <span className={meets3000 ? 'text-status-done' : ''}>
        노벨피아 3,000자 {meets3000 ? '충족 ✓' : `미달 (${(3000 - wordCount.noSpace).toLocaleString()}자)`}
      </span>
    </div>
  );
}
