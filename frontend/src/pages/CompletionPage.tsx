/**
 * 완결 관리 페이지 — D03-6 완결본 관리.
 * 완결 점검표(파생 읽기) + 완결본 스냅샷(명시적 생성·불변 보존).
 * 자동 완결 판정 없음 — 점검표는 작가가 판단할 사실 나열이다.
 */
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  api,
  type CompletionChecklist,
  type FinalEdition,
  type FinalEditionDetail,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/components/ui/toast';

const STAGE_LABELS: Record<string, string> = {
  planning: '기획',
  writing: '집필',
  revising: '퇴고',
  confirmed: '확정',
};

const DISPOSITION_LABELS: Record<string, string> = {
  resolved: '해결',
  intentional_unresolved: '의도적 미해결',
  side_story: '외전 이관',
  closed_unclassified: '미분류(닫힘)',
};

const SERIAL_LABELS: Record<string, string> = {
  ongoing: '연재중',
  hiatus: '휴재',
  completed: '완결',
};

function ChecklistSection({ checklist }: { checklist: CompletionChecklist }) {
  const f = checklist.foreshadows;
  return (
    <section aria-label="완결 점검표" className="rounded-md border p-4 space-y-3">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold">완결 점검표</h2>
        <Badge variant="outline">{SERIAL_LABELS[checklist.serial_state] ?? checklist.serial_state}</Badge>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
        <div>
          회차 {checklist.chapters.total}개 · 확정 {checklist.chapters.by_stage.confirmed ?? 0}
          {checklist.chapters.unconfirmed > 0 && (
            <span className="text-muted-foreground"> · 미확정 {checklist.chapters.unconfirmed}</span>
          )}
        </div>
        <div>
          미수용 감수 {checklist.pending_refine_runs}건
        </div>
        <div>
          파손 근거 링크 {checklist.broken_evidence_links}건
        </div>
        <div>복선 {f.total}개</div>
      </div>
      <div className="flex flex-wrap gap-1 text-xs">
        {(['planning', 'writing', 'revising', 'confirmed'] as const).map((s) => (
          <Badge key={s} variant="secondary">
            {STAGE_LABELS[s]} {checklist.chapters.by_stage[s] ?? 0}
          </Badge>
        ))}
        {Object.keys(DISPOSITION_LABELS).map((d) => (
          <Badge key={d} variant="outline">
            {DISPOSITION_LABELS[d]} {f.by_disposition[d] ?? 0}
          </Badge>
        ))}
      </div>
      {f.open.length > 0 && (
        <div className="text-sm">
          <span className="text-muted-foreground">미회수 복선:</span>{' '}
          {f.open.map((o) => o.title).join(', ')}
        </div>
      )}
      {checklist.finale_goals_missing_ending.length > 0 && (
        <div className="text-sm">
          <span className="text-muted-foreground">결말 의도 없는 최종화 목표:</span>{' '}
          {checklist.finale_goals_missing_ending.map((g) => g.title).join(', ')}
        </div>
      )}
    </section>
  );
}

function EditionDetail({ pid, edition }: { pid: number; edition: FinalEdition }) {
  const detailQuery = useQuery({
    queryKey: ['final-editions', pid, edition.id],
    queryFn: () => api.get<FinalEditionDetail>(`/projects/${pid}/final-editions/${edition.id}`),
  });
  const detail = detailQuery.data;
  if (detailQuery.isPending) return <p className="text-sm text-muted-foreground">불러오는 중…</p>;
  if (!detail) return null;
  return (
    <div className="space-y-3 border-t pt-3">
      <div className="space-y-1">
        <h3 className="text-xs font-semibold text-muted-foreground">매니페스트</h3>
        <ul className="text-xs space-y-0.5">
          {detail.manifest.map((m) => (
            <li key={m.chapter_id}>
              {m.title} · r{m.revision} · {STAGE_LABELS[m.flow_stage] ?? m.flow_stage} · {m.chars}자
            </li>
          ))}
          {detail.manifest.length === 0 && <li>회차 없음</li>}
        </ul>
      </div>
      <div className="space-y-1">
        <h3 className="text-xs font-semibold text-muted-foreground">원고 전문</h3>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-muted p-3 text-xs">
          {detail.content_md || '(빈 원고)'}
        </pre>
      </div>
    </div>
  );
}

export function CompletionPage() {
  const params = useParams();
  const pid = Number(params.pid);
  const queryClient = useQueryClient();
  const [label, setLabel] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const checklistQuery = useQuery({
    queryKey: ['completion-checklist', pid],
    queryFn: () => api.get<CompletionChecklist>(`/projects/${pid}/completion-checklist`),
  });
  const editionsQuery = useQuery({
    queryKey: ['final-editions', pid],
    queryFn: () => api.get<FinalEdition[]>(`/projects/${pid}/final-editions`),
  });

  const createMutation = useMutation({
    mutationFn: (l: string | null) =>
      api.post<FinalEditionDetail>(`/projects/${pid}/final-editions`, { label: l }),
    onSuccess: () => {
      setLabel('');
      queryClient.invalidateQueries({ queryKey: ['final-editions', pid] });
      queryClient.invalidateQueries({ queryKey: ['completion-checklist', pid] });
      toast('완결본을 생성했습니다');
    },
    onError: () => toast('완결본 생성에 실패했습니다'),
  });

  const deleteMutation = useMutation({
    mutationFn: (eid: number) => api.del(`/projects/${pid}/final-editions/${eid}`),
    onSuccess: () => {
      setExpandedId(null);
      queryClient.invalidateQueries({ queryKey: ['final-editions', pid] });
      queryClient.invalidateQueries({ queryKey: ['completion-checklist', pid] });
      toast('완결본을 삭제했습니다');
    },
    onError: () => toast('완결본 삭제에 실패했습니다'),
  });

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <div className="flex items-center gap-3">
        <Link to="/" className="text-sm text-muted-foreground hover:underline">
          ← 작품 목록
        </Link>
        <h1 className="text-lg font-semibold">완결 관리</h1>
      </div>

      {checklistQuery.isPending ? (
        <p className="text-sm text-muted-foreground">점검표 불러오는 중…</p>
      ) : checklistQuery.data ? (
        <ChecklistSection checklist={checklistQuery.data} />
      ) : null}

      <section aria-label="완결본" className="rounded-md border p-4 space-y-3">
        <h2 className="text-sm font-semibold">완결본 스냅샷</h2>
        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="edition-label">라벨(선택)</Label>
            <Input
              id="edition-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="예: 1차 완결본"
              maxLength={200}
            />
          </div>
          <Button
            onClick={() => createMutation.mutate(label.trim() || null)}
            disabled={createMutation.isPending}
          >
            완결본 생성
          </Button>
        </div>

        {editionsQuery.isPending && (
          <p className="text-sm text-muted-foreground">완결본 불러오는 중…</p>
        )}
        {editionsQuery.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">아직 완결본이 없습니다.</p>
        )}
        <ul className="space-y-2">
          {editionsQuery.data?.map((e) => (
            <li key={e.id} className="rounded-md border p-3 space-y-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  aria-expanded={expandedId === e.id}
                  className="text-sm font-medium hover:underline"
                  onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
                >
                  {e.label ?? `완결본 ${e.id}`}
                </button>
                <Badge variant="outline">{SERIAL_LABELS[e.serial_state] ?? e.serial_state}</Badge>
                <span className="text-xs text-muted-foreground">
                  {new Date(e.created_at).toLocaleString('ko-KR')} · 회차 {e.chapter_count} · {e.total_chars}자
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  className="ml-auto text-destructive"
                  onClick={() => deleteMutation.mutate(e.id)}
                  disabled={deleteMutation.isPending}
                >
                  삭제
                </Button>
              </div>
              {expandedId === e.id && <EditionDetail pid={pid} edition={e} />}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
