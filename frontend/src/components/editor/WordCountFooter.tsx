import { useEditorStore } from '@/stores/editorStore';

/**
 * FR-104 — 글자 수 푸터(S-203). 공백제외 + 노벨피아 모드 병행 표시.
 * 노벨피아 모드는 공백+문장부호·특수문자 제외 집계(부록06)이며,
 * PLUS 3,000자 판정은 이 노벨피아 기준 값으로 한다.
 */
export function WordCountFooter() {
  const wordCount = useEditorStore((s) => s.wordCount);
  const meets3000 = wordCount.novelpia >= 3000;

  return (
    <div className="flex items-center gap-3 border-t border-border bg-card px-4 py-1.5 text-xs text-muted-foreground">
      <span className="font-mono tabular-nums">글자 {wordCount.total.toLocaleString()}</span>
      <span className="font-mono font-bold tabular-nums text-foreground">
        공백제외 {wordCount.noSpace.toLocaleString()}
      </span>
      <span
        className="font-mono tabular-nums"
        title="노벨피아 모드: 공백·문장부호·특수문자 제외 집계"
      >
        노벨피아 {wordCount.novelpia.toLocaleString()}
      </span>
      <span className={meets3000 ? 'text-status-done' : ''}>
        노벨피아 3,000자{' '}
        {meets3000 ? '충족 ✓' : `미달 (${(3000 - wordCount.novelpia).toLocaleString()}자)`}
      </span>
    </div>
  );
}
