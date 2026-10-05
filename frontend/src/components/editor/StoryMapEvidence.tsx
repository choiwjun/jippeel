import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { StoryReviewEditor, type ReviewDecision } from './StoryReview';

export type View = 'relations' | 'foreshadows' | 'review';
export interface Source { id: number; title: string; position: number; revision: number; future: boolean }
export interface Evidence {
  id: string; kind: 'relation' | 'relationship_change' | 'foreshadow' | 'stale_memory' | 'goal_drift';
  label: string; excerpt: string; basis: string; source: Source | null;
  from_id?: number | null; to_id?: number | null;
  from_name: string | null; to_name: string | null;
  planned: Source | null;
  review_key: string | null; evidence_token: string | null; review_text: string | null; latest_decision: ReviewDecision | null;
  planted: Source | null; resolved: Source | null; registered_status: string | null;
  source_revision: number | null;
  visibility: 'draft' | 'approved' | 'retired' | null;
  disposition: 'resolved' | 'intentional_unresolved' | 'side_story' | null;
}
export interface Result {
  project_id: number; chapter_id: number; chapter_revision: number; view: View;
  total: number; offset: number; next_offset: number | null; items: Evidence[];
}
const labels: Record<View, string> = { relations: '관계', foreshadows: '복선', review: '변경 검토' };
const dispositionLabels = { resolved: '해결', intentional_unresolved: '의도적 미해결', side_story: '외전 이관' };
const explanations: Record<View, string> = {
  relations: '작품의 관계 설정과 선택 회차까지의 승인 변화 기록입니다. 시점 없는 관계 설정은 과거 상태를 뜻하지 않습니다.',
  foreshadows: '작품 전체의 등록된 설치·예정 회수·실제 회수 기록입니다. 예정 회수는 작가 계획입니다. 선택 회차 이후의 기록에는 별도 표시가 붙습니다.',
  review: '작품 전체의 기억·목표 중 원문이나 연결 근거가 달라진 항목입니다. 내용을 검토한 뒤 갱신해 주세요.',
};

export function StoryMapEvidence({ pid, chapterId, onBrowse }: {
  pid: number; chapterId: number; onBrowse: (chapterId: number) => void;
}) {
  const [view, setView] = useState<View | null>(null);
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ['story-map', pid, 'evidence', chapterId, view, offset],
    queryFn: ({ signal }) => api.get<Result>(`/projects/${pid}/story-map/evidence?chapter_id=${chapterId}&view=${view}&offset=${offset}`, { signal }),
    enabled: view !== null, staleTime: 0,
  });
  const sourceButton = (source: Source | null, label = '근거 회차') => source
    ? <button type="button" className="max-w-full break-words text-left text-primary underline underline-offset-2 focus-visible:outline focus-visible:outline-2"
        onClick={() => onBrowse(source.id)}>{label}: {source.position}. {source.title || '제목 없음'} · 원고 v{source.revision}{source.future ? ' · 선택 회차 이후' : ''}</button>
    : <span className="text-muted-foreground">{label}: 시점 미등록</span>;
  return <section aria-label="회차 관련 근거" className="mt-4 border-t border-border pt-3 text-xs">
    <div role="group" aria-label="관련 근거 보기" className="mb-3 flex flex-wrap gap-1">
      <Button size="sm" variant={view === null ? 'secondary' : 'ghost'} aria-pressed={view === null} onClick={() => setView(null)}>목표만 보기</Button>
      {(Object.keys(labels) as View[]).map(v => <Button key={v} size="sm" variant={view === v ? 'secondary' : 'ghost'} aria-pressed={view === v}
        onClick={() => { setView(v); setOffset(0); }}>{labels[v]}</Button>)}
    </div>
    {view && <>
      <h4 className="mb-2 font-semibold">{labels[view]} · {view === 'review' ? '작품 전체' : '살펴보는 회차 기준'}</h4>
      <p className="mb-3 text-muted-foreground">{explanations[view]}</p>
      {query.isPending && <p role="status">근거를 불러오는 중…</p>}
      {query.isFetching && !query.isPending && <p role="status">근거 갱신 중…</p>}
      {query.isError && <div role="alert">근거를 불러오지 못했습니다. {query.data && '아래는 마지막 조회 결과입니다.'}
        <Button size="sm" variant="outline" onClick={() => void query.refetch()}>근거 다시 불러오기</Button>
      </div>}
      {query.data && <>
        <p className="mb-2">{query.data.total}개 · 선택 회차 원고 v{query.data.chapter_revision} 기준 조회</p>
        {query.data.items.length === 0 && <p className="py-3 text-muted-foreground">이 범위에서 표시할 근거가 없습니다.</p>}
        <ul className="space-y-3">
          {query.data.items.map(item => <li key={item.id} className="space-y-2 rounded-md border border-border bg-background p-3">
            <p className="break-words font-medium">{item.label}</p>
            {(item.kind === 'relation' || item.kind === 'relationship_change') && <div role="group" className="flex items-center justify-between gap-2" aria-label="인물 연결">
              <span className="min-w-0 flex-1 break-words rounded bg-muted p-2 text-center">{item.from_name}</span>
              <span aria-hidden="true">↔</span>
              <span className="min-w-0 flex-1 break-words rounded bg-muted p-2 text-center">{item.to_name}</span>
            </div>}
            <p className="text-muted-foreground">{item.basis}</p>
            {item.kind === 'stale_memory' && <p className="font-medium">{item.visibility === 'approved' ? '승인 기억' : '미승인 초안'} · 재검토 필요</p>}
            {item.kind === 'foreshadow' && <>
              <p>현재 등록 상태: {item.registered_status} <span className="text-muted-foreground">· 과거 시점의 상태와 다를 수 있음</span></p>
              <p>처분: {item.disposition ? dispositionLabels[item.disposition] : '미등록'}</p>
              <ol aria-label="복선 설치·회수 타임라인" className="space-y-2 border-l-2 border-primary/40 pl-3">
                <li>{sourceButton(item.planted, '설치')}</li>
                <li className="border-l-2 border-dashed pl-2">{sourceButton(item.planned, '예정 회수 · 작가 계획')}</li>
                <li>{sourceButton(item.resolved, item.disposition === 'intentional_unresolved' || item.disposition === 'side_story' ? '처분 기록 회차' : '실제 회수')}</li>
              </ol>
            </>}
            {item.source_revision !== null && <p>기준 원고 v{item.source_revision} → 현재 {item.source ? `v${item.source.revision}` : '근거 없음'}</p>}
            {item.excerpt && <p className="whitespace-pre-wrap break-words">{item.excerpt}</p>}
            {item.kind !== 'foreshadow' && item.source && sourceButton(item.source, '근거 살펴보기')}
            {item.review_key && item.evidence_token && item.review_text !== null && <StoryReviewEditor key={`${pid}:${item.review_key}`} pid={pid}
              item={{ id: item.review_key, evidence_token: item.evidence_token, review_text: item.review_text, latest_decision: item.latest_decision }} />}
          </li>)}
        </ul>
        <div className="my-3 flex items-center justify-between gap-2">
          <Button size="sm" variant="outline" disabled={query.data.offset === 0}
            onClick={() => setOffset(Math.max(0, query.data!.offset - 50))}>근거 이전</Button>
          <span>{query.data.total ? `${query.data.offset + 1}–${query.data.offset + query.data.items.length}` : '0'} / {query.data.total}</span>
          <Button size="sm" variant="outline" disabled={query.data.next_offset === null}
            onClick={() => setOffset(query.data!.next_offset ?? 0)}>근거 다음</Button>
        </div>
      </>}
      {view === 'review' && <Link className="text-primary underline" to={`/projects/${pid}/memory`}>기억 관리에서 검토하기</Link>}
      {view === 'foreshadows' && <Link className="text-primary underline" to={`/projects/${pid}/foreshadows`}>복선 관리 열기</Link>}
      {view === 'relations' && <Link className="text-primary underline" to={`/projects/${pid}/cognitive`}>인지·사건 기록 검토하기</Link>}
    </>}
  </section>;
}
