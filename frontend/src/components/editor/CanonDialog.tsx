/**
 * canon 모순 검사 Dialog — 고도화 G-023 + 이력(G-041).
 * 현재 회차가 캐릭터·세계관·복선 설정과 모순되는 후보를 LLM으로 검사해 나열.
 * 원고 자동 수정 없음 — 작가 판단 대상. 검사 결과는 이력으로 재조회 가능.
 */
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Badge, type BadgeVariant } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { toast } from '@/components/ui/toast';

interface CanonIssue {
  quote: string;
  reason: string;
  severity: 'info' | 'warn' | 'error';
}

interface CanonCheckResponse {
  run_id: number;
  chapter_id: number;
  model: string | null;
  issues: CanonIssue[];
  checked_context: Record<string, number>;
}

interface CanonRun {
  id: number;
  chapter_id: number;
  model: string | null;
  issues_json: CanonIssue[] | null;
  context_json: Record<string, number> | null;
  created_at: string;
}

const severityLabel: Record<CanonIssue['severity'], string> = {
  error: '치명', warn: '주의', info: '참고',
};
const severityVariant: Record<CanonIssue['severity'], BadgeVariant> = {
  error: 'done', warn: 'revising', info: 'secondary',
};

export function CanonDialog({ chapterId }: { chapterId: number | null }) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  const run = useMutation({
    mutationFn: () => api.post<CanonCheckResponse>('/canon-check', { chapter_id: chapterId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['canon-runs', chapterId] });
    },
    onError: (e) => toast(`모순 검사 실패: ${(e as Error).message}`, 'error'),
  });

  const historyQuery = useQuery({
    queryKey: ['canon-runs', chapterId],
    queryFn: () => api.get<CanonRun[]>(`/canon-check/runs?chapter_id=${chapterId}`),
    enabled: chapterId !== null && open,
  });

  const ctx = run.data?.checked_context;
  const ctxSummary = ctx
    ? `캐릭터 ${ctx.characters ?? 0} · 로어 ${ctx.lore ?? 0} · 복선 ${ctx.foreshadows ?? 0} · 독자 인지 ${ctx.audience_known ?? 0}`
    : '';

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button
        size="sm"
        variant="outline"
        disabled={chapterId === null}
        onClick={() => setOpen(true)}
        aria-label="canon 모순 검사"
      >
        모순 검사
      </Button>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>연속성(모순) 검사</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <p className="text-[11px] text-muted-foreground">
            현재 회차가 캐릭터 설정·세계관·복선(시간축·위치 포함)과 모순되는 지점을 검사합니다.
            원고는 절대 자동 수정되지 않습니다.
          </p>
          <Button
            disabled={chapterId === null || run.isPending}
            onClick={() => run.mutate()}
          >
            {run.isPending ? '검사 중… (수십 초 소요)' : '🔍 검사 실행'}
          </Button>

          {run.data && (
            <div className="flex flex-col gap-2">
              <p className="text-[11px] text-muted-foreground">
                검사 대상 — {ctxSummary}
              </p>
              {run.data.issues.length === 0 ? (
                <Alert variant="info">
                  <AlertDescription>모순 후보가 없습니다.</AlertDescription>
                </Alert>
              ) : (
                run.data.issues.map((issue, i) => (
                  <div key={i} className="rounded-md border border-border p-2">
                    <div className="mb-1 flex items-center gap-2">
                      <Badge variant={severityVariant[issue.severity]}>
                        {severityLabel[issue.severity]}
                      </Badge>
                    </div>
                    <p className="text-xs font-medium">“{issue.quote}”</p>
                    <p className="mt-1 text-xs text-muted-foreground">{issue.reason}</p>
                  </div>
                ))
              )}
            </div>
          )}

          <details className="rounded-md border border-border p-2">
            <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">
              검사 이력 ({historyQuery.data?.length ?? 0})
            </summary>
            <div className="mt-2 flex max-h-40 flex-col gap-1.5 overflow-y-auto">
              {(historyQuery.data ?? []).map((r) => (
                <div key={r.id} className="flex items-center justify-between gap-2 text-xs">
                  <span className="text-muted-foreground">
                    {new Date(r.created_at).toLocaleString('ko-KR')}
                  </span>
                  <span>{(r.issues_json ?? []).length}건 · {r.model ?? '-'}</span>
                </div>
              ))}
              {(historyQuery.data ?? []).length === 0 && (
                <p className="text-xs text-muted-foreground">이력 없음</p>
              )}
            </div>
          </details>
        </div>
      </DialogContent>
    </Dialog>
  );
}
