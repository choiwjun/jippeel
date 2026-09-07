/**
 * S6 윤문 리포트 (설계서 §2.6 / §3.2).
 *
 * P4: 사용자 수락/거절 결정 — 자동 덮어쓰기 없음.
 * C-2 (FR-505): 변경률 ≥ 50% → [수락] 미노출(disabled 아닌 제거), 재실행/폐기만.
 *   - 30~50% (warn): 수락 가능 + 경고 Alert.
 * FR-503: 진단 span taxonomy ID(A~J) 카테고리 색 하이라이트.
 * FR-504: jsdiff 문자 단위 diff 병렬 뷰.
 */
import { forwardRef, useMemo, useRef, useState, type ReactNode } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { diffChars } from 'diff';
import { api, type ChapterDetail, type RefineResult, type RefineSpan, type TaxonomyCategory } from '@/lib/api';
import { useAiPanelStore } from '@/stores/aiPanelStore';
import { useEditorStore } from '@/stores/editorStore';
import { beginManuscriptReplacement, completeManuscriptReplacement, flushManuscriptDraft } from '@/lib/manuscriptDrafts';
import { toast } from '@/components/ui/toast';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Select } from '@/components/ui/select';

const CAT_LABELS: Record<TaxonomyCategory, string> = {
  A: '번역투', B: '영어인용', C: '구조적패턴', D: '관용구', E: '리듬',
  F: '수식중복', G: 'Hedging', H: '접속사', I: '형식명사', J: '시각장식',
};

type RunState = {
  result: RefineResult;
  routeOverride: '' | 'light' | 'standard' | 'heavy';
};

export function RefineReport() {
  const chapterId = useEditorStore((s) => s.chapterId);
  const projectId = useEditorStore((s) => s.projectId);
  const close = useAiPanelStore((s) => s.close);
  const queryClient = useQueryClient();

  const [run, setRun] = useState<RunState | null>(null);
  const [routeOverride, setRouteOverride] = useState<'' | 'light' | 'standard' | 'heavy'>('');
  const [view, setView] = useState<'diff' | 'spans'>('diff');

  const execute = useMutation({
    mutationFn: async () => {
      if (chapterId === null || projectId === null) throw new Error('회차를 먼저 선택하세요.');
      const flushed = await flushManuscriptDraft(projectId, chapterId);
      return api.post<RefineResult>('/refine', {
        chapter_id: chapterId,
        expected_revision: flushed.detail.revision,
        force_route: routeOverride === '' ? null : routeOverride,
      });
    },
    onSuccess: (result) => {
      setRun({ result, routeOverride });
      toast(`윤문 실행 완료 — 변경률 ${(result.changed_ratio * 100).toFixed(1)}%`, 'info');
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  const accept = useMutation({
    mutationFn: async (runId: number) => {
      if (chapterId === null || projectId === null) throw new Error('회차를 먼저 선택하세요.');
      await flushManuscriptDraft(projectId, chapterId);
      const token = beginManuscriptReplacement(projectId, chapterId);
      const detail = await api.post<ChapterDetail>(`/refine/runs/${runId}/accept`);
      return { detail, token };
    },
    onSuccess: ({ detail, token }, runId) => {
      if (chapterId !== null && projectId !== null) {
        const result = completeManuscriptReplacement(projectId, chapterId, detail, token);
        queryClient.setQueryData(['chapter', chapterId], detail);
        queryClient.invalidateQueries({ queryKey: ['chapters', projectId] });
        if (result === 'late_edit') {
          toast('윤문 수락 결과는 서버에 반영됐지만 새 입력이 있어 로컬 원고를 보존했습니다.', 'warning');
        } else {
          toast('윤문 수락됨 — 회차 본문이 교체되었습니다.', 'success');
        }
      }
      queryClient.invalidateQueries({ queryKey: ['refine-run', runId] });
      setRun(null);
      close();
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  const reject = useMutation({
    mutationFn: (runId: number) => api.post(`/refine/runs/${runId}/reject`),
    onSuccess: () => {
      toast('윤문을 폐기했습니다. 기록만 남습니다.', 'info');
      setRun(null);
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  if (chapterId === null) {
    return (
      <p className="text-sm text-muted-foreground">
        좌측에서 회차를 선택한 뒤 윤문을 실행하세요.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <Alert variant="info">
        <AlertDescription>
          본 결과는 글을 다듬기 위한 제안입니다. AI 탐지 회피를 의미하지 않습니다.
        </AlertDescription>
      </Alert>

      {!run ? (
        <section className="rounded-md border border-border p-3">
          <h3 className="mb-2 text-xs font-semibold text-muted-foreground">윤문 실행</h3>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Select
                aria-label="윤문 강도"
                value={routeOverride}
                onChange={(e) => setRouteOverride(e.target.value as typeof routeOverride)}
              >
                <option value="">강도 자동 (권장)</option>
                <option value="light">light — 가볍게</option>
                <option value="standard">standard — 표준</option>
                <option value="heavy">heavy — 강하게</option>
              </Select>
            </div>
            <Button disabled={execute.isPending} onClick={() => execute.mutate()}>
              🔍 윤문 실행
            </Button>
          </div>
          {execute.isPending && (
            <p className="mt-2 text-sm text-muted-foreground">윤문 파이프라인 실행 중…</p>
          )}
        </section>
      ) : (
        <RefineResultView
          run={run}
          view={view}
          setView={setView}
          onRerun={() => { setRun(null); execute.reset(); }}
          onAccept={() => accept.mutate(run.result.run_id)}
          onDiscard={() => reject.mutate(run.result.run_id)}
          accepting={accept.isPending}
        />
      )}
    </div>
  );
}

function RefineResultView({
  run, view, setView, onRerun, onAccept, onDiscard, accepting,
}: {
  run: RunState;
  view: 'diff' | 'spans';
  setView: (v: 'diff' | 'spans') => void;
  onRerun: () => void;
  onAccept: () => void;
  onDiscard: () => void;
  accepting: boolean;
}) {
  const r = run.result;
  const ratioPct = Math.min(100, Math.round(r.changed_ratio * 1000) / 10);

  // FR-504 — jsdiff 문자 단위 파트 (원문/수정본 공유 파트 리스트)
  const parts = useMemo(() => diffChars(r.original, r.refined), [r.original, r.refined]);

  // 진단 span → 원문 오프셋 구간으로 정렬·병합 렌더 데이터
  const spans = useMemo(
    () => [...r.spans].sort((a, b) => a.start - b.start),
    [r.spans],
  );

  const gateBar =
    r.gate === 'pass' ? 'bg-status-done'
    : r.gate === 'warn' ? 'bg-warning'
    : 'bg-destructive';

  const blocked = r.gate === 'block' || r.status === 'blocked';

  // 카테고리별 집계 (진단 패널)
  const byCat = new Map<TaxonomyCategory, number>();
  for (const s of r.spans) byCat.set(s.category, (byCat.get(s.category) ?? 0) + 1);

  return (
    <div className="flex flex-col gap-3">
      {/* 요약 헤더 */}
      <p className="text-xs text-muted-foreground">
        경도: {r.route_hint} · 진단 {r.spans.length}건 · 변경률{' '}
        <span className="font-mono tabular-nums font-semibold">{ratioPct.toFixed(1)}%</span>
      </p>

      {/* 변경률 게이트 게이지 (FR-505) — 30% 경고선 / 50% 차단선 */}
      <section className="rounded-md border border-border p-3">
        <h3 className="mb-2 text-xs font-semibold text-muted-foreground">
          변경률 게이트 — 30% 경고 / 50% 차단
        </h3>
        <div className="relative">
          <Progress value={ratioPct} barClassName={gateBar} />
          {/* 30% 경고 눈금 */}
          <span className="absolute top-[-2px] h-[14px] w-px bg-warning" style={{ left: '30%' }} aria-hidden="true" />
          {/* 50% 차단 눈금 */}
          <span className="absolute top-[-2px] h-[14px] w-px bg-destructive" style={{ left: '50%' }} aria-hidden="true" />
        </div>
        <div className="mt-1.5 flex justify-between text-[10px] text-muted-foreground">
          <span>0%</span>
          <span className="text-warning">30% 경고</span>
          <span className="text-destructive">50% 차단</span>
          <span>100%</span>
        </div>
      </section>

      {/* 게이트 분기 Alert */}
      {r.gate === 'warn' && (
        <Alert variant="warning">
          <AlertDescription>30~50% — 과윤문 가능성이 있습니다. 신중히 검토한 뒤 결정하세요.</AlertDescription>
        </Alert>
      )}
      {blocked && (
        <Alert variant="error">
          <AlertDescription>
            50% 초과 — 자동 수락 차단. 새로 쓰기를 권장합니다. 선택지는 윤문 재실행 또는 폐기뿐입니다.
          </AlertDescription>
        </Alert>
      )}

      {/* 뷰 전환: 병렬 diff / 진단 스팬 */}
      <div className="flex items-center gap-2" role="tablist" aria-label="리포트 보기 전환">
        <Button size="sm" variant={view === 'diff' ? 'default' : 'outline'} onClick={() => setView('diff')} aria-selected={view === 'diff'} role="tab">
          변경 비교
        </Button>
        <Button size="sm" variant={view === 'spans' ? 'default' : 'outline'} onClick={() => setView('spans')} aria-selected={view === 'spans'} role="tab">
          진단 스팬 ({r.spans.length})
        </Button>
        <span className="ml-auto text-xs text-muted-foreground">
          원문 {r.original.length.toLocaleString()}자 · 결과 {blocked ? '—' : `${r.refined.length.toLocaleString()}자`}
        </span>
      </div>

      {/* S6 — 성공 응답이면 spans 유무·게이트 무관하게 병렬 비교 영역은 항상 렌더 */}
      {view === 'diff' ? (
        <>
          {(blocked || r.refined === '') && (
            <Alert variant="default">
              <AlertDescription>차단된 실행은 수정본을 표시하지 않습니다.</AlertDescription>
            </Alert>
          )}
          <ParallelDiff
            parts={parts}
            rightPlaceholder={
              r.refined === ''
                ? blocked
                  ? '차단된 실행 — 수정본 미표시'
                  : '수정본 없음'
                : undefined
            }
          />
        </>
      ) : (
        <SpanHighlight original={r.original} spans={spans} />
      )}

      {/* 진단 카테고리 범례/집계 (FR-503) */}
      {r.spans.length > 0 && (
        <section className="rounded-md border border-border p-3">
          <h3 className="mb-2 text-xs font-semibold text-muted-foreground">진단 카테고리 (taxonomy A~J)</h3>
          <div className="flex flex-wrap gap-1.5">
            {[...byCat.entries()].map(([cat, n]) => (
              <Badge key={cat} variant="outline" className="gap-1">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: `hsl(var(--cat-${cat}))` }} aria-hidden="true" />
                {cat} {CAT_LABELS[cat]} · {n}건
              </Badge>
            ))}
          </div>
        </section>
      )}

      {/* 액션 바 — C-2: block이면 수락 버튼 자체를 노출하지 않는다(강제 수락 경로 삭제) */}
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-border p-3">
        {!blocked ? (
          <>
            <Button disabled={accepting} onClick={onAccept}>✓ 수락 (에디터에 반영)</Button>
            <Button variant="ghost" onClick={onDiscard}>✗ 거절</Button>
            <span className="w-full text-xs text-muted-foreground">
              수락 시 회차 본문이 수정본으로 교체됩니다. 거절 시 기록만 남습니다.
            </span>
          </>
        ) : (
          <>
            <Button variant="outline" onClick={onRerun}>🔄 윤문 재실행 (강도 변경)</Button>
            <Button variant="ghost" onClick={onDiscard}>🗑 폐기</Button>
            <span className="w-full text-xs text-destructive">
              ※ 50% 초과 시 본 결과는 반영 불가. 재실행 또는 폐지만 선택할 수 있습니다. (C-2)
            </span>
          </>
        )}
      </div>

      {!blocked && (
        <div className="flex justify-end">
          <Button size="sm" variant="ghost" onClick={onRerun}>🔄 다시 실행 (강도 변경)</Button>
        </div>
      )}
    </div>
  );
}

/** FR-504 병렬 diff — 좌: 원문(삭제 빨강) / 우: 수정본(추가 녹색), 스크롤 동기 */
function ParallelDiff({
  parts,
  rightPlaceholder,
}: {
  parts: Array<{ value: string; added?: boolean; removed?: boolean }>;
  /** 수정본이 비어 있을 때 우측 패널에 표시할 안내 문구(패널 자체는 항상 렌더) */
  rightPlaceholder?: string;
}) {
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);

  const syncScroll = (from: HTMLDivElement | null, to: HTMLDivElement | null) => {
    if (!from || !to || syncing.current) return;
    syncing.current = true;
    to.scrollTop = from.scrollTop;
    requestAnimationFrame(() => { syncing.current = false; });
  };

  return (
    <div className="grid grid-cols-2 gap-2">
      <DiffPane
        ref={leftRef}
        title="원문"
        onScroll={() => syncScroll(leftRef.current, rightRef.current)}
        render={(cls) =>
          parts.map((p, i) =>
            p.added ? null : (
              <span key={i} className={p.removed ? cls.del : undefined}>{p.value}</span>
            ),
          )
        }
      />
      <DiffPane
        ref={rightRef}
        title="수정본"
        onScroll={() => syncScroll(rightRef.current, leftRef.current)}
        render={(cls) =>
          rightPlaceholder !== undefined ? (
            <span className="text-muted-foreground">{rightPlaceholder}</span>
          ) : (
            parts.map((p, i) =>
              p.removed ? null : (
                <span key={i} className={p.added ? cls.add : undefined}>{p.value}</span>
              ),
            )
          )
        }
      />
    </div>
  );
}

interface DiffPaneProps {
  title: string;
  onScroll: () => void;
  render: (classes: { add: string; del: string }) => ReactNode;
}

const DiffPane = forwardRef<HTMLDivElement, DiffPaneProps>(function DiffPane(
  { title, onScroll, render }, ref,
) {
  return (
    <div className="flex min-w-0 flex-col rounded-md border border-border">
      <h4 className="border-b border-border px-2 py-1.5 text-xs font-semibold text-muted-foreground">{title}</h4>
      <div
        ref={ref}
        onScroll={onScroll}
        tabIndex={0}
        role="region"
        aria-label={`${title} 비교 보기`}
        className="thin-scroll max-h-80 min-h-32 overflow-y-auto whitespace-pre-wrap break-words p-2 font-serif text-sm leading-relaxed"
      >
        {render({
          add: 'rounded-sm bg-diff-add-bg text-diff-add decoration-diff-add underline',
          del: 'rounded-sm bg-diff-del-bg text-diff-del line-through opacity-80',
        })}
      </div>
    </div>
  );
});

/** FR-503 — 원문에 category A~J 색상 span 하이라이트 (hover 시 진단 메시지) */
function SpanHighlight({ original, spans }: { original: string; spans: RefineSpan[] }) {
  const nodes: ReactNode[] = [];
  let cursor = 0;
  spans.forEach((s, i) => {
    if (s.start > cursor) nodes.push(<span key={`t${i}`}>{original.slice(cursor, s.start)}</span>);
    const seg = original.slice(s.start, s.end);
    nodes.push(
      <mark
        key={`s${i}`}
        title={s.message ? `[${CAT_LABELS[s.category]}] ${s.message}` : `[${CAT_LABELS[s.category]}]`}
        style={{
          background: `hsl(var(--cat-${s.category}) / 0.15)`,
          color: `hsl(var(--cat-${s.category}))`,
          borderBottom: `2px solid hsl(var(--cat-${s.category}))`,
        }}
        className="rounded-sm px-0.5"
      >
        {seg}
      </mark>,
    );
    cursor = s.end;
  });
  if (cursor < original.length) nodes.push(<span key="tail">{original.slice(cursor)}</span>);

  return (
    <div
      tabIndex={0}
      role="region"
      aria-label="원문 진단 하이라이트"
      className="thin-scroll max-h-96 min-h-32 overflow-y-auto whitespace-pre-wrap break-words rounded-md border border-border p-2 font-serif text-sm leading-relaxed"
    >
      {nodes.length > 0 ? nodes : <span className="text-muted-foreground">탐지된 패턴 없음</span>}
    </div>
  );
}
