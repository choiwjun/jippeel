/**
 * 복선 관리 — 고도화 G-020/G-021.
 * "설치 → 회수" 상태로 복선을 관리한다. 미회수(설치) 복선은 AI 패널의
 * "미회수 복선 자동 포함" 체크박스로 집필 컨텍스트에 자동 주입된다(G-022).
 */
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';

export interface Foreshadow {
  id: number;
  project_id: number;
  title: string;
  content: string | null;
  keywords: string[] | null;
  status: '설치' | '회수' | '보류';
  audience_knows?: boolean;
  planted_chapter_id: number | null;
  resolved_chapter_id: number | null;
}

interface ChapterMeta {
  id: number;
  title: string;
}

interface SuggestCandidate {
  title: string;
  content: string | null;
  keywords: string[] | null;
}

/** G-048 회수 리마인드 응답 */
interface ReminderItem {
  id: number;
  title: string;
  content: string | null;
  chapters_since_mentioned: number | null;
  last_mentioned_chapter_title: string | null;
  stale: boolean;
}

interface ReminderResponse {
  window: number;
  latest_chapter: { id: number; title: string } | null;
  items: ReminderItem[];
}

const STATUSES: Foreshadow['status'][] = ['설치', '회수', '보류'];
const statusVariant: Record<Foreshadow['status'], string> = {
  설치: 'text-warning',
  회수: 'text-success',
  보류: 'text-muted-foreground',
};

export function ForeshadowsPage() {
  const params = useParams();
  const pid = Number(params.pid);
  const queryClient = useQueryClient();

  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [keywords, setKeywords] = useState('');
  const [audienceKnows, setAudienceKnows] = useState(false);
  const [filter, setFilter] = useState<Foreshadow['status'] | null>(null);
  const [candidates, setCandidates] = useState<SuggestCandidate[] | null>(null);

  const foreshadowsQuery = useQuery({
    queryKey: ['foreshadows', pid],
    queryFn: () => api.get<Foreshadow[]>(`/projects/${pid}/foreshadows`),
  });
  const chaptersQuery = useQuery({
    queryKey: ['chapters', pid],
    queryFn: () => api.get<ChapterMeta[]>(`/projects/${pid}/chapters`),
  });
  // G-048 — 미회수 복선 회수 리마인드 (최근 5화 기준)
  const reminderQuery = useQuery({
    queryKey: ['foreshadow-reminder', pid],
    queryFn: () => api.get<ReminderResponse>(`/projects/${pid}/foreshadows/reminder?window=5`),
    enabled: foreshadowsQuery.isSuccess,
  });
  const staleItems = (reminderQuery.data?.items ?? []).filter((r) => r.stale);
  const all = foreshadowsQuery.data ?? [];
  const rows = useMemo(
    () => (filter ? all.filter((f) => f.status === filter) : all),
    [all, filter],
  );
  const installedCount = all.filter((f) => f.status === '설치').length;

  const createPayload = useMutation({
    mutationFn: (payload: { title: string; content: string | null; keywords: string[] }) =>
      api.post<Foreshadow>(`/projects/${pid}/foreshadows`, {
        title: payload.title,
        content: payload.content,
        keywords: payload.keywords,
        status: '설치',
        audience_knows: audienceKnows,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['foreshadows', pid] });
      toast('복선을 등록했습니다.', 'success');
    },
    onError: (e) => toast(`복선 등록 실패: ${(e as Error).message}`, 'error'),
  });
  const create = useMutation({
    mutationFn: () =>
      createPayload.mutateAsync({
        title: title.trim(),
        content: content.trim() || null,
        keywords: keywords.split(',').map((k) => k.trim()).filter(Boolean),
      }),
    onSuccess: () => {
      setTitle(''); setContent(''); setKeywords(''); setAudienceKnows(false);
    },
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: Foreshadow['status'] }) =>
      api.patch<Foreshadow>(`/foreshadows/${id}`, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['foreshadows', pid] }),
    onError: (e) => toast(`상태 변경 실패: ${(e as Error).message}`, 'error'),
  });

  const toggleAudience = useMutation({
    mutationFn: ({ id, audience_knows }: { id: number; audience_knows: boolean }) =>
      api.patch<Foreshadow>(`/foreshadows/${id}`, { audience_knows }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['foreshadows', pid] }),
    onError: (e) => toast(`변경 실패: ${(e as Error).message}`, 'error'),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/foreshadows/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['foreshadows', pid] }),
    onError: (e) => toast(`삭제 실패: ${(e as Error).message}`, 'error'),
  });

  /** G-046 — 복선 후보 자동 추출(후보만 반환, 등록은 명시 클릭) */
  const suggest = useMutation({
    mutationFn: (chapterId: number) =>
      api.post<{ chapter_id: number; candidates: SuggestCandidate[] }>(
        `/projects/${pid}/foreshadows/suggest`, { chapter_id: chapterId }),
    onSuccess: (body) => {
      setCandidates(body.candidates);
      toast(body.candidates.length === 0
        ? '새로운 떡밥 후보가 없습니다.'
        : `후보 ${body.candidates.length}건을 추출했습니다 — 확인 후 등록하세요.`, 'info');
    },
    onError: (e) => toast(`떡밥 추출 실패: ${(e as Error).message}`, 'error'),
  });

  return (
    <div className="mx-auto flex h-full max-w-[820px] flex-col gap-4 overflow-y-auto px-6 py-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold">복선 관리</h1>
        <Badge variant="secondary">미회수 {installedCount}</Badge>
        <div className="ml-auto flex gap-1">
          <Button
            size="sm" variant={filter === null ? 'default' : 'outline'}
            onClick={() => setFilter(null)}
          >
            전체
          </Button>
          {STATUSES.map((s) => (
            <Button
              key={s} size="sm"
              variant={filter === s ? 'default' : 'outline'}
              onClick={() => setFilter(s)}
            >
              {s}
            </Button>
          ))}
        </div>
      </header>

      {/* G-048 회수 리마인드 */}
      {staleItems.length > 0 && (
        <section className="rounded-md border border-warning/40 bg-warning/5 p-3">
          <h2 className="mb-1 text-sm font-semibold">⏳ 회수 리마인드 — 최근 {(reminderQuery.data?.window ?? 5)}화 동안 언급 없음</h2>
          <p className="mb-2 text-[11px] text-muted-foreground">
            설치 상태인데 오래 잊힌 복선입니다. 회수할지·유예할지(상태를 '보류'로)는 작가가 판단하세요.
          </p>
          <ul className="flex flex-col gap-1">
            {staleItems.map((r) => (
              <li key={r.id} className="text-xs">
                · <span className="font-medium">{r.title}</span>
                <span className="text-muted-foreground">
                  {r.chapters_since_mentioned === null
                    ? ' — 본문에 한 번도 언급되지 않음'
                    : ` — 마지막 언급: ${r.last_mentioned_chapter_title ?? '?'}(${r.chapters_since_mentioned}화 전)`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 등록 폼 */}
      <section className="rounded-md border border-border p-3">
        <div className="grid grid-cols-[1fr_auto] gap-2">
          <Input
            aria-label="복선 제목"
            placeholder="복선 제목 (예: 검의 진짜 주인)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <Button
            disabled={create.isPending || !title.trim()}
            onClick={() => create.mutate()}
          >
            + 복선 등록
          </Button>
        </div>
        <Textarea
          aria-label="복선 내용"
          className="mt-2"
          rows={2}
          placeholder="어떤 복선인지, 어디서 회수할 예정인지…"
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        <Input
          aria-label="키워드 (쉼표 구분)"
          className="mt-2"
          placeholder="키워드 쉼표 구분 (예: 검, 검의 주인)"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
        />
        <div className="mt-2 flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              aria-label="독자가 이미 알게 된 사실"
              checked={audienceKnows}
              onChange={(e) => setAudienceKnows(e.target.checked)}
            />
            독자가 이미 알게 된 사실 (G-045 — 모순 검사 시 인지 중복 확인용)
          </label>
        </div>

        {/* G-046 — AI 떡밥 추출 */}
        <div className="mt-2 flex items-center gap-2">
          <select
            aria-label="떡밥 추출 대상 회차"
            className="h-8 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            defaultValue=""
            onChange={(e) => {
              const cid = Number(e.target.value);
              if (cid) suggest.mutate(cid);
              e.target.value = '';
            }}
          >
            <option value="">🪝 AI로 떡밥 추출할 회차 선택…</option>
            {(chaptersQuery.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.title.trim() || `${c.id}화`}
              </option>
            ))}
          </select>
          {suggest.isPending && <span className="text-xs text-muted-foreground">추출 중…</span>}
        </div>
        {candidates && candidates.length > 0 && (
          <div className="mt-2 rounded-md border border-border p-2">
            <p className="mb-1 text-xs font-semibold">떡밥 후보 — 확인 후 등록하세요</p>
            {candidates.map((c, i) => (
              <div key={i} className="flex items-start gap-2 border-b border-border py-1.5 last:border-b-0">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium">{c.title}</p>
                  {c.content && <p className="text-[11px] text-muted-foreground">{c.content}</p>}
                </div>
                <Button
                  size="sm" variant="outline" className="h-6 px-2 text-[11px]"
                  disabled={createPayload.isPending}
                  onClick={() => {
                    createPayload.mutate({
                      title: c.title,
                      content: c.content,
                      keywords: c.keywords ?? [],
                    });
                    setCandidates((prev) => (prev ?? []).filter((_, j) => j !== i));
                  }}
                >
                  등록
                </Button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 목록 */}
      <section className="flex flex-col gap-2">
        {foreshadowsQuery.isPending && (
          <p className="text-sm text-muted-foreground">불러오는 중…</p>
        )}
        {rows.length === 0 && !foreshadowsQuery.isPending && (
          <p className="text-sm text-muted-foreground">
            등록된 복선이 없습니다. 집필 중 떠오른 떡밥을 여기에 남겨두면, AI 집필 시
            미회수 복선이 자동으로 컨텍스트에 포함됩니다.
          </p>
        )}
        {rows.map((f) => (
          <article
            key={f.id}
            className="flex items-start gap-2 rounded-md border border-border p-3"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h2 className="truncate text-sm font-medium">{f.title}</h2>
                <span className={cn('text-xs font-semibold', statusVariant[f.status])}>
                  {f.status}
                </span>
                {f.audience_knows !== undefined && (
                  <label className="flex items-center gap-1 text-[10px] text-muted-foreground">
                    <input
                      type="checkbox"
                      aria-label={`독자 인지: ${f.title}`}
                      checked={f.audience_knows}
                      onChange={(e) => toggleAudience.mutate({
                        id: f.id, audience_knows: e.target.checked })}
                    />
                    독자 인지
                  </label>
                )}
              </div>
              {f.content && (
                <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{f.content}</p>
              )}
              {(f.keywords?.length ?? 0) > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {f.keywords!.map((k) => (
                    <Badge key={k} variant="secondary" className="text-[10px]">{k}</Badge>
                  ))}
                </div>
              )}
            </div>
            <select
              aria-label={`복선 상태 변경: ${f.title}`}
              className="h-8 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={f.status}
              onChange={(e) =>
                setStatus.mutate({ id: f.id, status: e.target.value as Foreshadow['status'] })}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <Button
              size="sm" variant="ghost" className="text-destructive"
              disabled={remove.isPending}
              onClick={() => remove.mutate(f.id)}
              aria-label={`복선 삭제: ${f.title}`}
            >
              삭제
            </Button>
          </article>
        ))}
      </section>

      <Label className="text-[11px] text-muted-foreground">
        복선은 원고를 자동으로 수정하지 않습니다 — 집필 시 참고 컨텍스트로만 사용됩니다.
      </Label>
    </div>
  );
}
