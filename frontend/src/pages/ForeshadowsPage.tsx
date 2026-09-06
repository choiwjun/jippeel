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
  planted_chapter_id: number | null;
  resolved_chapter_id: number | null;
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
  const [filter, setFilter] = useState<Foreshadow['status'] | null>(null);

  const foreshadowsQuery = useQuery({
    queryKey: ['foreshadows', pid],
    queryFn: () => api.get<Foreshadow[]>(`/projects/${pid}/foreshadows`),
  });
  const all = foreshadowsQuery.data ?? [];
  const rows = useMemo(
    () => (filter ? all.filter((f) => f.status === filter) : all),
    [all, filter],
  );
  const installedCount = all.filter((f) => f.status === '설치').length;

  const create = useMutation({
    mutationFn: () =>
      api.post<Foreshadow>(`/projects/${pid}/foreshadows`, {
        title: title.trim(),
        content: content.trim() || null,
        keywords: keywords.split(',').map((k) => k.trim()).filter(Boolean),
        status: '설치',
      }),
    onSuccess: () => {
      setTitle(''); setContent(''); setKeywords('');
      queryClient.invalidateQueries({ queryKey: ['foreshadows', pid] });
      toast('복선을 등록했습니다.', 'success');
    },
    onError: (e) => toast(`복선 등록 실패: ${(e as Error).message}`, 'error'),
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: Foreshadow['status'] }) =>
      api.patch<Foreshadow>(`/foreshadows/${id}`, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['foreshadows', pid] }),
    onError: (e) => toast(`상태 변경 실패: ${(e as Error).message}`, 'error'),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/foreshadows/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['foreshadows', pid] }),
    onError: (e) => toast(`삭제 실패: ${(e as Error).message}`, 'error'),
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
