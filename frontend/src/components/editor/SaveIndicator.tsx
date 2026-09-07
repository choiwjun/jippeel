import { useEffect, useState } from 'react';
import { useEditorStore } from '@/stores/editorStore';

function relativeTime(ts: number): string {
  const rtf = new Intl.RelativeTimeFormat('ko', { numeric: 'auto' });
  const diffSec = Math.round((ts - Date.now()) / 1000);
  if (Math.abs(diffSec) < 60) return rtf.format(diffSec, 'second');
  const diffMin = Math.round(diffSec / 60);
  if (Math.abs(diffMin) < 60) return rtf.format(diffMin, 'minute');
  return rtf.format(Math.round(diffMin / 60), 'hour');
}

/** FR-106 — "저장됨 · 방금 전" / "저장 중…" / "저장 실패". 5초마다 상대시간 갱신. */
export function SaveIndicator() {
  const saveState = useEditorStore((s) => s.saveState);
  const lastSavedAt = useEditorStore((s) => s.lastSavedAt);
  const [, tick] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => tick((n) => n + 1), 5000);
    return () => window.clearInterval(id);
  }, []);

  if (saveState === 'saving') return <span className="text-xs text-muted-foreground">저장 중…</span>;
  if (saveState === 'error')
    return <span className="text-xs text-destructive">저장 실패 — 원고 보존됨</span>;
  if (saveState === 'conflict')
    return <span className="text-xs text-destructive">저장 충돌 — 원고 확인 필요</span>;
  if (saveState === 'dirty')
    return <span className="text-xs text-muted-foreground">저장 대기</span>;
  if (lastSavedAt)
    return (
      <span className="text-xs text-muted-foreground" aria-live="polite">
        저장됨 · {relativeTime(lastSavedAt)}
      </span>
    );
  return <span className="text-xs text-muted-foreground">저장 대기</span>;
}
