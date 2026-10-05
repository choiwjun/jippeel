import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, type ChapterDetail, type ChapterGoalPayload, volumeLabel } from '@/lib/api';
import { flushManuscriptDraft, getManuscriptDraft, getManuscriptDraftState } from '@/lib/manuscriptDrafts';
import type { StoryMapCounts, StoryMapData, StoryMapNode, StoryMapScope } from '@/lib/storyMap';
import { useEditorStore } from '@/stores/editorStore';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { StoryMapEvidence } from './StoryMapEvidence';
import { StoryReviewHistory } from './StoryReview';
import { StoryVisualOverview } from './StoryVisualOverview';

const STAGES = { planning: '기획', writing: '집필', revising: '퇴고', confirmed: '확정' };
const emptySubscribe = () => () => {};
const emptySnapshot = () => null;
const SAVE_LABELS = {
  saved: '저장된 원고 기준', dirty: '입력 중 · 지도는 마지막 저장본 기준',
  saving: '저장 중 · 지도는 마지막 저장본 기준', error: '저장 실패 · 지도는 마지막 저장본 기준',
  conflict: '저장 충돌 · 지도는 마지막 저장본 기준',
};
const GOAL_FIELDS: [keyof ChapterGoalPayload, string][] = [
  ['emotion_goal', '감정 목표'], ['core_events', '핵심 사건'], ['character_choices', '인물 선택'],
  ['cost', '대가'], ['prohibitions', '금지 사항'], ['next_hook', '다음 전개'],
  ['ending_intent', '결말 의도'], ['scene_type', '장면 유형'], ['target_chars_novelpia', '목표 글자 수'],
];

function Counts({ counts }: { counts: StoryMapCounts }) {
  return <section aria-label="집필 진행률" className="space-y-2 rounded-md bg-muted/40 p-3 text-xs">
    <p>선택 범위 총 {counts.total}회 · 계획 회차 추가·삭제 시 분모도 변경됩니다.</p>
    {(['written', 'confirmed'] as const).map((key) => <div key={key}>
      <p className="mb-1">{key === 'written' ? '작성' : '확정'} {counts[key]} / {counts.total}회</p>
      <Progress aria-label={key === 'written' ? '작성 회차 비율' : '확정 회차 비율'}
        value={counts.total ? 100 * counts[key] / counts.total : 0}
        barClassName={key === 'confirmed' ? 'bg-emerald-600' : undefined} />
    </div>)}
    <p className="text-muted-foreground">작성: 저장본의 노벨피아 집계 글자 수 1자 이상. 확정: 집필 단계가 ‘확정’인 회차.</p>
  </section>;
}

function GoalDetail({ node }: { node: StoryMapNode }) {
  const fields = GOAL_FIELDS.filter(([key]) => {
    const value = node.goal?.[key];
    return value != null && value !== '' && (!Array.isArray(value) || value.length > 0);
  });
  return <div className="space-y-2 text-xs">
    <p>저장 원고 v{node.revision} · {node.word_count.toLocaleString()}자 · 장면 {node.scene_count}개</p>
    <p className="font-medium">작가 계획 {node.goal_version !== null ? `· 목표 v${node.goal_version}` : '· 목표 미등록'}</p>
    <p className="text-muted-foreground">목표는 예정된 전개입니다. 본문에서 실제로 일어났다는 뜻은 아닙니다.</p>
    {node.goal_base_revision !== null && node.goal_base_revision !== node.revision &&
      <p className="text-amber-700 dark:text-amber-400">목표의 기준 원고 v{node.goal_base_revision}과 현재 저장본이 다릅니다.</p>}
    {fields.length ? <dl className="space-y-2">
      {fields.map(([key, label]) => <div key={key}>
        <dt className="font-medium">{label}</dt>
        <dd className="whitespace-pre-wrap break-words text-muted-foreground">
          {Array.isArray(node.goal?.[key])
            ? <ul className="list-disc pl-4">{(node.goal[key] as string[]).map((v, i) => <li key={i}>{v}</li>)}</ul>
            : String(node.goal?.[key])}
        </dd>
      </div>)}
    </dl> : <p className="text-muted-foreground">아직 작성한 목표 내용이 없습니다.</p>}
  </div>;
}

export function StoryMapPanel({ pid, chapterId, onNavigate }: {
  pid: number; chapterId: number | null; onNavigate: () => void;
}) {
  const coordinator = useMemo(() => chapterId === null ? null : getManuscriptDraft(pid, chapterId), [pid, chapterId]);
  const draft = useSyncExternalStore(coordinator?.subscribe ?? emptySubscribe,
    coordinator?.getSnapshot ?? emptySnapshot, coordinator?.getSnapshot ?? emptySnapshot);
  const saveState = draft?.saveState ?? 'saved';
  const [scope, setScope] = useState<StoryMapScope>('near');
  const [anchor, setAnchor] = useState(chapterId);
  const [offset, setOffset] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState(chapterId);
  const [list, setList] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [navigationError, setNavigationError] = useState('');
  const [moving, setMoving] = useState(false);
  const alive = useRef(true);
  const movingRef = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['story-map', pid, anchor, scope, offset],
    queryFn: ({ signal }) => api.get<StoryMapData>(`/projects/${pid}/story-map?scope=${scope}${offset !== null ? `&offset=${offset}` : ''}${anchor !== null ? `&anchor_id=${anchor}` : ''}`, { signal }),
    staleTime: 0,
  });
  const data = query.data;
  const selected = data?.nodes.find((n) => n.id === selectedId) ?? null;
  const groups = new Map<string, StoryMapNode[]>();
  for (const node of data?.nodes ?? []) {
    const key = String(node.volume);
    groups.set(key, [...(groups.get(key) ?? []), node]);
  }

  async function navigate(node: StoryMapNode) {
    if (movingRef.current) return;
    movingRef.current = true;
    setMoving(true); setNavigationError('');
    const stillHere = () => alive.current && useEditorStore.getState().projectId === pid
      && useEditorStore.getState().chapterId === chapterId;
    try {
      // Flush the originating coordinator; looking at future nodes never changes AI identity.
      if (chapterId !== null) {
        await flushManuscriptDraft(pid, chapterId);
        if (getManuscriptDraftState(pid, chapterId).hasUnsaved) {
          throw new Error('현재 원고의 저장 실패·충돌을 해결한 후 이동해 주세요.');
        }
      }
      if (!stillHere()) return;
      const target = await api.get<ChapterDetail>(`/chapters/${node.id}`);
      if (!stillHere()) return;
      if (target.project_id !== pid) throw new Error('이 작품의 회차가 아닙니다.');
      // Edits may have arrived while fetching the target. Never abandon that newer draft.
      if (chapterId !== null && getManuscriptDraftState(pid, chapterId).hasUnsaved) {
        throw new Error('새로 입력한 내용을 저장한 후 다시 이동해 주세요.');
      }
      useEditorStore.getState().setContext(pid, node.id);
      onNavigate();
    } catch (error) {
      if (stillHere()) setNavigationError(error instanceof Error ? error.message : '회차를 열지 못했습니다.');
    } finally {
      movingRef.current = false;
      if (alive.current) setMoving(false);
    }
  }

  return <aside id="story-map" aria-label="스토리 지도" className="thin-scroll h-full min-h-0 overflow-y-auto rounded-lg border border-border bg-card p-4 pb-40">
    <div className="mb-3 flex items-center justify-between gap-2">
      <h2 className="font-semibold">스토리 지도</h2>
      <a className="text-xs text-primary underline underline-offset-2" href="/story-demo.html" target="_blank" rel="noreferrer">예시로 먼저 보기 ↗</a>
      <Button variant="ghost" size="sm" disabled={query.isFetching} onClick={() => void queryClient.cancelQueries({ queryKey: ['story-map', pid] }).then(() => queryClient.invalidateQueries({ queryKey: ['story-map', pid] }))}>새로고침</Button>
    </div>
    <p role="status" className="mb-3 text-xs text-muted-foreground">{SAVE_LABELS[saveState]}{query.isFetching ? ' · 지도 갱신 중…' : ''}</p>
    <div role="group" aria-label="지도 범위" className="mb-3 flex flex-wrap gap-1">
      {([['near', '현재 주변'], ['volume', '선택 권'], ['all', '작품 전체']] as const).map(([value, label]) =>
        <Button key={value} size="sm" variant={scope === value ? 'secondary' : 'ghost'} aria-pressed={scope === value}
          onClick={() => { setScope(value); setOffset(null); setSelectedId(value === 'near' ? chapterId : null); setAnchor(chapterId); setList(false); }}>{label}</Button>)}
    </div>
    {data && scope === 'volume' && <label className="mb-3 block text-xs">권 선택
      <select className="ml-2 max-w-full rounded border border-border bg-background p-1"
        value={String(data.volumes.find((v) => data.nodes[0]?.volume === v.volume)?.first_chapter_id ?? '')}
        onChange={(event) => { setAnchor(Number(event.target.value)); setOffset(null); setSelectedId(null); }}>
        {data.volumes.map((v) => <option key={String(v.volume)} value={v.first_chapter_id}>{volumeLabel(v.volume)} · {v.total}회</option>)}
      </select>
    </label>}
    {query.isError && <div role="alert" className="my-3 text-sm text-destructive">
      지도를 불러오지 못했습니다. {query.error.message} 위의 새로고침으로 다시 시도하세요.
      {data && <p>아래 내용은 마지막으로 조회한 지도입니다.</p>}
      {anchor !== null && query.error instanceof ApiError && query.error.status === 404 &&
        <Button variant="outline" size="sm" onClick={() => {
          setAnchor(null); setOffset(null); setSelectedId(null); setScope('near');
        }}>지도 처음부터 열기</Button>}
    </div>}
    {query.isPending && <p className="text-sm">지도를 불러오는 중…</p>}
    {data && <>
      <details className="rounded border border-border px-3 py-2 text-xs">
        <summary className="cursor-pointer">집필 진행 · 작성 {data.counts.written}/{data.counts.total}회 · 확정 {data.counts.confirmed}/{data.counts.total}회</summary>
        <Counts counts={data.counts} />
      </details>
      <div className="my-3 flex items-center justify-between gap-2 text-xs">
        <p className="text-muted-foreground">{scope === 'near'
          ? (data.anchor_id === chapterId ? '앞 2회 · 현재 · 다음 최대 5회' : '탐색 기준 회차의 앞 2회 · 뒤 최대 5회')
          : '권 → 회차 순서'}<br />연결선은 회차 순서입니다.</p>
        <Button size="sm" variant="outline" aria-pressed={list} onClick={() => setList(!list)}>{list ? '흐름도 보기' : '목록 보기'}</Button>
      </div>
      {data.counts.total === 0 && <p className="py-6 text-sm text-muted-foreground">아직 회차가 없습니다. 회차를 추가하면 지도에 나타납니다.</p>}
      {!list && <StoryVisualOverview pid={pid} data={data} currentId={chapterId} selectedId={selectedId}
        onSelect={id => { setSelectedId(id); setNavigationError(''); }}
        onBrowse={id => { setAnchor(id); setSelectedId(id); setScope('near'); setOffset(null); }} />}
      {list && [...groups].map(([key, nodes]) => <section key={key} className="mb-3">
        <button type="button" className="mb-2 rounded px-1 text-sm font-medium focus-visible:outline focus-visible:outline-2"
          aria-expanded={!collapsed.has(key)} onClick={() => setCollapsed((old) => {
            const next = new Set(old); if (next.has(key)) next.delete(key); else next.add(key); return next;
          })}>{collapsed.has(key) ? '▸' : '▾'} {volumeLabel(nodes[0].volume)} · 표시 {nodes.length}회</button>
        {!collapsed.has(key) && <ol className="space-y-1" aria-label={`${volumeLabel(nodes[0].volume)} 회차 순서`}>
          {nodes.map((node, index) => <li key={node.id}>
            {!list && index > 0 && <svg aria-hidden="true" width="24" height="22" className="mx-auto text-muted-foreground">
              <path d="M12 0V18M7 13L12 18L17 13" fill="none" stroke="currentColor" strokeDasharray={node.flow_stage === 'planning' ? '3 2' : undefined} />
            </svg>}
            <button type="button" aria-pressed={selectedId === node.id} aria-current={node.id === chapterId ? 'step' : undefined}
              onClick={() => { setSelectedId(node.id); setNavigationError(''); }}
              className={`w-full rounded-lg border p-3 text-left text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring ${node.flow_stage === 'planning' ? 'border-dashed' : ''} ${node.id === chapterId ? 'border-primary ring-1 ring-primary' : 'border-border'} ${selectedId === node.id ? 'bg-primary/10' : 'bg-background hover:bg-muted'}`}>
              <span className="mb-1 block break-words font-medium">{node.position}. {node.title || '제목 없음'}</span>
              <span className="block text-muted-foreground">{node.id === chapterId ? '현재 집필 · ' : ''}{STAGES[node.flow_stage]} · {node.word_count.toLocaleString()}자 · 원고 v{node.revision}</span>
              <span className="mt-1 block truncate">계획: {node.goal?.core_events?.[0] || node.goal?.emotion_goal || '목표 내용 없음'}</span>
            </button>
          </li>)}
        </ol>}
      </section>)}
      {list && scope !== 'near' && <div className="my-3 flex items-center justify-between gap-2 text-xs">
        <Button size="sm" variant="outline" disabled={data.offset === 0} onClick={() => { setOffset(Math.max(0, data.offset - 25)); setSelectedId(null); }}>이전</Button>
        <span>{data.counts.total ? `${data.offset + 1}–${data.offset + data.nodes.length} / ${data.counts.total}회` : '0회'}</span>
        <Button size="sm" variant="outline" disabled={data.next_offset === null} onClick={() => { setOffset(data.next_offset ?? 0); setSelectedId(null); }}>다음</Button>
      </div>}
      {(scope === 'near' || list) && <section aria-label="선택 회차 상세" className="mt-4 rounded-lg border border-border p-3">
        {selected ? <>
          <h3 className="mb-2 break-words text-sm font-semibold">{selected.title || '제목 없음'} · {selected.id === chapterId ? '현재 집필 회차' : '살펴보는 회차'}</h3>
          <details><summary className="cursor-pointer text-xs">목표와 상세 근거 펼치기</summary>
          <GoalDetail node={selected} />
          <StoryMapEvidence key={selected.id} pid={pid} chapterId={selected.id}
            onBrowse={(id) => { setAnchor(id); setSelectedId(id); setScope('near'); setOffset(null); }} />
          </details>
          <Button className="mt-3" size="sm" disabled={moving} onClick={() => void navigate(selected)}>
            {moving ? '저장 확인 중…' : selected.id === chapterId ? '원고로 돌아가기' : '이 회차 집필'}
          </Button>
        </> : <p className="text-xs text-muted-foreground">회차를 선택하면 목표와 저장 정보를 볼 수 있습니다.</p>}
        {navigationError && <p role="alert" className="mt-2 text-xs text-destructive">{navigationError}</p>}
      </section>}
    </>}
    <StoryReviewHistory key={pid} pid={pid} />
  </aside>;
}
