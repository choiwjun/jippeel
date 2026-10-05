import { useId, useState, type KeyboardEvent, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, volumeLabel } from '@/lib/api';
import type { StoryMapData, StoryMapNode } from '@/lib/storyMap';
import { Button } from '@/components/ui/button';
import type { Evidence, Result, Source } from './StoryMapEvidence';
import { StoryWorkbench } from './StoryWorkbench';

const ink = 'hsl(var(--foreground))';
const muted = 'hsl(var(--muted-foreground))';
const paper = 'hsl(var(--card))';
const border = 'hsl(var(--border))';
const primary = 'hsl(var(--primary))';
const stages = { planning: '기획', writing: '집필', revising: '퇴고', confirmed: '확정' };
const short = (value: string, size = 18) => value.length > size ? `${value.slice(0, size)}…` : value;
function activate(event: KeyboardEvent<SVGGElement>, action: () => void) {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); action(); }
}
function Card({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <section className="story-chart-card min-w-0 rounded-xl border border-border bg-background/50 p-3" aria-label={title}>
    <h3 className="text-sm font-semibold">{title}</h3>
    <p className="mb-3 mt-1 text-xs text-muted-foreground">{description}</p>
    {children}
  </section>;
}

function FlowGraph({ nodes, currentId, selectedId, onSelect }: {
  nodes: StoryMapNode[]; currentId: number | null; selectedId: number | null; onSelect: (id: number) => void;
}) {
  const marker = useId().replace(/:/g, '');
  const columns = Math.min(4, nodes.length);
  const width = Math.max(280, columns * 244 + 16);
  const height = Math.ceil(nodes.length / columns) * 174 + 20;
  const locations = nodes.map((_, i) => {
    const row = Math.floor(i / columns);
    const col = row % 2 ? columns - 1 - i % columns : i % columns;
    return { x: 16 + col * 244, y: 16 + row * 174 };
  });
  return <div className="overflow-x-auto rounded-lg bg-muted/20">
    <svg role="group" aria-label="회차 순서와 전개 계획 흐름도" viewBox={`0 0 ${width} ${height}`}
      className="w-full" style={{ minWidth: Math.min(width, 720) }}>
      <defs><marker id={marker} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10z" fill={muted} />
      </marker></defs>
      {nodes.slice(1).map((node, i) => {
        const a = locations[i], b = locations[i + 1];
        const path = a.y === b.y
          ? (b.x > a.x ? `M${a.x + 216} ${a.y + 64} H${b.x - 4}` : `M${a.x} ${a.y + 64} H${b.x + 220}`)
          : `M${a.x + 108} ${a.y + 132} V${b.y - 4}`;
        return <path key={node.id} d={path} fill="none" stroke={muted} strokeWidth="2"
          strokeDasharray={node.flow_stage === 'planning' ? '5 4' : undefined} markerEnd={`url(#${marker})`} />;
      })}
      {nodes.map((node, i) => {
        const { x, y } = locations[i];
        const current = node.id === currentId, selected = node.id === selectedId;
        const stale = node.goal_base_revision !== null && node.goal_base_revision !== node.revision;
        return <g key={node.id} transform={`translate(${x} ${y})`} role="button" tabIndex={0}
          aria-label={`${node.position}. ${node.title || '제목 없음'}, ${current ? '현재 집필, ' : ''}${stages[node.flow_stage]}, 계획 ${node.goal?.core_events?.join(', ') || node.goal?.emotion_goal || '미등록'}`}
          aria-pressed={selected} onClick={() => onSelect(node.id)} onKeyDown={e => activate(e, () => onSelect(node.id))}
          className="cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">
          <title>{`${node.title} — 계획: ${node.goal?.core_events?.join(' / ') || node.goal?.emotion_goal || '목표 없음'}`}</title>
          <rect width="216" height="132" rx="12" fill={paper} stroke={current || selected ? primary : border}
            strokeWidth={current ? 3 : selected ? 2 : 1} strokeDasharray={node.flow_stage === 'planning' ? '6 3' : undefined} />
          <text x="12" y="22" fill={current ? primary : muted} fontSize="12" fontWeight="600">{current ? '● 현재 집필' : volumeLabel(node.volume)} · {stages[node.flow_stage]}</text>
          <text x="12" y="47" fill={ink} fontSize="14" fontWeight="600">{node.position}. {short(node.title || '제목 없음', 11)}</text>
          <text x="12" y="73" fill={muted} fontSize="12">계획 · {short(node.goal?.core_events?.[0] || node.goal?.emotion_goal || '미등록', 12)}</text>
          <text x="12" y="96" fill={muted} fontSize="12">{node.word_count.toLocaleString()}자 · 장면 {node.scene_count}개</text>
          <text x="12" y="118" fill={stale ? '#b45309' : selected ? primary : muted} fontSize="11">{stale ? '△ 목표 재검토 필요' : selected ? '선택한 회차 · 아래에서 상세 보기' : `원고 v${node.revision} · 클릭하여 살펴보기`}</text>
        </g>;
      })}
    </svg>
  </div>;
}

function WritingChart({ nodes, currentId, onSelect }: { nodes: StoryMapNode[]; currentId: number | null; onSelect: (id: number) => void }) {
  const max = Math.max(1000, ...nodes.map(n => n.word_count));
  const width = Math.max(900, nodes.length * 32 + 70), plot = width - 80;
  const step = plot / nodes.length;
  return <div className="overflow-x-auto">
    <svg role="group" aria-label="현재 조회 회차의 저장 글자 수 막대그래프" viewBox={`0 0 ${width} 220`} className="w-full" style={{ minWidth: 500 }}>
      {[0, 0.5, 1].map(f => <g key={f}>
        <line x1="55" x2={width - 20} y1={170 - f * 130} y2={170 - f * 130} stroke={border} />
        <text x="48" y={174 - f * 130} textAnchor="end" fill={muted} fontSize="11">{Math.round(max * f).toLocaleString()}</text>
      </g>)}
      {nodes.map((node, i) => {
        const x = 55 + i * step, h = node.word_count / max * 130;
        return <g key={node.id} role="button" tabIndex={0} aria-label={`${node.position}. ${node.title}, 저장 ${node.word_count}자`}
          onClick={() => onSelect(node.id)} onKeyDown={e => activate(e, () => onSelect(node.id))}
          className="cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">
          <title>{`${node.title}: ${node.word_count.toLocaleString()}자 · ${stages[node.flow_stage]}`}</title>
          <rect x={x} y="25" width={step} height="178" fill="transparent" />
          <rect x={x + step * 0.16} y={170 - h} width={step * 0.68} height={Math.max(h, 1)} rx="3" fill={node.id === currentId ? primary : muted} opacity={node.id === currentId ? 1 : 0.6} />
          <text x={x + step / 2} y="190" textAnchor="middle" fill={node.id === currentId ? primary : muted} fontSize="11">{node.position}</text>
        </g>;
      })}
      <text x="55" y="16" fill={muted} fontSize="11">저장 글자 수(자)</text>
      <text x={width - 20} y="212" textAnchor="end" fill={muted} fontSize="11">회차 순서 →</text>
    </svg>
    <p className="text-xs text-muted-foreground">강조색: 현재 집필 회차 · 노벨피아 글자 수 기준 · 막대를 누르면 회차 선택</p>
  </div>;
}

function RelationNetwork({ items, onBrowse }: { items: Evidence[]; onBrowse: (id: number) => void }) {
  const arrowId = useId().replace(/:/g, '');
  const [mode, setMode] = useState<'relation' | 'relationship_change'>('relation');
  const [focus, setFocus] = useState<string | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const candidates = items.filter(i => i.kind === mode && i.from_name && i.to_name);
  const safePage = Math.min(page, Math.max(0, Math.ceil(candidates.length / 8) - 1));
  const edges = candidates.slice(safePage * 8, safePage * 8 + 8);
  const key = (item: Evidence, side: 'from' | 'to') => item[`${side}_id`] != null ? `id:${item[`${side}_id`]}` : `legacy:${item.id}:${side}`;
  const names = new Map<string, string>();
  edges.forEach(i => { names.set(key(i, 'from'), i.from_name!); names.set(key(i, 'to'), i.to_name!); });
  const positions = new Map([...names].map(([id, name], i) => {
    const angle = 2 * Math.PI * i / names.size - Math.PI / 2;
    return [id, { x: 320 + 225 * Math.cos(angle), y: 205 + 143 * Math.sin(angle), name }];
  }));
  const selection = edges.find(i => i.id === chosen);
  return <>
    <div role="group" aria-label="관계 근거 구분" className="mb-2 flex flex-wrap gap-1">
      {([['relation', '현재 작가 설정'], ['relationship_change', '승인된 변화']] as const).map(([value, label]) => <Button key={value} size="sm"
        variant={mode === value ? 'secondary' : 'ghost'} aria-pressed={mode === value}
        onClick={() => { setMode(value); setFocus(null); setChosen(null); setPage(0); }}>{label}</Button>)}
    </div>
    <p className="text-xs text-muted-foreground">{mode === 'relation' ? '시점 정보 없는 현재 설정입니다. 과거 관계를 뜻하지 않습니다.' : '기준 회차까지 승인된 변화의 기록입니다. 관계의 최종 상태를 뜻하지 않습니다.'}</p>
    {edges.length ? <>
      <div className="overflow-x-auto">
        <svg role="group" aria-label="인물 연결 관계망" viewBox="0 0 640 410" className="w-full" style={{ minWidth: 500 }}>
          <defs><marker id={arrowId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0 0 L10 5 L0 10z" fill={muted} />
          </marker></defs>
          {edges.map((item, i) => {
            const a = positions.get(key(item, 'from'))!, b = positions.get(key(item, 'to'))!;
            const emphasized = !focus || focus === key(item, 'from') || focus === key(item, 'to');
            // Curves separate parallel records; self-relations get a visible loop.
            const bend = (i % 3 - 1) * 35;
            const cx = (a.x + b.x) / 2 + bend, cy = (a.y + b.y) / 2 + bend;
            const self = key(item, 'from') === key(item, 'to');
            const length = Math.hypot(b.x - cx, b.y - cy) || 1;
            const endX = b.x - (b.x - cx) / length * 24, endY = b.y - (b.y - cy) / length * 24;
            const d = self ? `M${a.x + 14} ${a.y - 14} C${a.x + 80} ${a.y - 90} ${a.x - 80} ${a.y - 90} ${a.x - 17} ${a.y - 18}`
              : `M${a.x} ${a.y} Q${cx} ${cy} ${endX} ${endY}`;
            return <g key={item.id} opacity={emphasized ? 1 : 0.2}>
              <path d={d} fill="none" stroke={item.id === chosen ? primary : muted} strokeWidth={item.id === chosen ? 3 : 1.5} strokeDasharray={mode === 'relation' ? '5 4' : undefined} markerEnd={`url(#${arrowId})`} />
              <text x={self ? a.x : (a.x + 2 * cx + b.x) / 4} y={self ? a.y - 64 : (a.y + 2 * cy + b.y) / 4 - 5} textAnchor="middle" fontSize="11" fill={ink}
                stroke={paper} strokeWidth="4" paintOrder="stroke">{i + 1}. {short(item.label, 9)}</text>
            </g>;
          })}
          {[...positions].map(([id, p]) => <g key={id} role="button" tabIndex={0}
            aria-label={`${p.name}${id.startsWith('legacy:') ? ', 이름 기반 과거 기록' : `, 인물 ${id.slice(3)}`}, 연결 강조`}
            aria-pressed={focus === id} onClick={() => setFocus(focus === id ? null : id)} onKeyDown={e => activate(e, () => setFocus(focus === id ? null : id))}
            className="cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">
            <title>{`${p.name} · ${id.startsWith('legacy:') ? '인물 ID 없는 이름 기반 기록' : `인물 #${id.slice(3)}`}`}</title>
            <circle cx={p.x} cy={p.y} r="20" fill={paper} stroke={focus === id ? primary : muted} strokeWidth={focus === id ? 3 : 1.5} />
            <text x={p.x} y={p.y + 4} textAnchor="middle" fill={ink} fontSize="12" fontWeight="600">{short(p.name, 2)}</text>
            <text x={p.x} y={p.y + 37} textAnchor="middle" fill={ink} fontSize="12">{short(p.name, 10)}{id.startsWith('legacy:') ? '*' : ''}</text>
          </g>)}
        </svg>
      </div>
      <div className="max-h-36 space-y-1 overflow-y-auto" aria-label="그래프 관계 목록">{edges.map((item, i) => <button type="button" key={item.id}
        aria-pressed={chosen === item.id} className="block w-full rounded p-1 text-left text-xs hover:bg-muted focus-visible:outline focus-visible:outline-2"
        onClick={() => setChosen(item.id)}>{i + 1}. {item.from_name} → {item.to_name} · {item.label}</button>)}</div>
      {selection && <div className="mt-2 rounded bg-muted p-2 text-xs">
        <p className="whitespace-pre-wrap break-words">{selection.excerpt || selection.label}</p>
        {selection.source && <button className="mt-1 underline" onClick={() => onBrowse(selection.source!.id)}>근거 {selection.source.position}. {selection.source.title} 살펴보기</button>}
      </div>}
      <div className="mt-2 flex items-center justify-between gap-1 text-xs">
        <Button size="sm" variant="ghost" disabled={safePage === 0} onClick={() => { setPage(safePage - 1); setFocus(null); }}>연결 이전</Button>
        <span>{safePage * 8 + 1}–{safePage * 8 + edges.length} / 조회된 {candidates.length}개</span>
        <Button size="sm" variant="ghost" disabled={(safePage + 1) * 8 >= candidates.length} onClick={() => { setPage(safePage + 1); setFocus(null); }}>연결 다음</Button>
      </div>
      <p className="text-xs text-muted-foreground">인물을 누르면 연결 강조 · * 이름만 남은 기록은 동일인 여부가 불명확해 기록별로 나눕니다.</p>
    </> : <p className="py-10 text-center text-xs text-muted-foreground">이 조회 페이지에 표시할 {mode === 'relation' ? '관계 설정' : '승인 변화'}이 없습니다.</p>}
  </>;
}

function ForeshadowTimeline({ items, focusPosition, onBrowse }: { items: Evidence[]; focusPosition: number; onBrowse: (id: number) => void }) {
  const [page, setPage] = useState(0);
  const records = items.filter(i => i.kind === 'foreshadow');
  const safePage = Math.min(page, Math.max(0, Math.ceil(records.length / 6) - 1));
  const rows = records.slice(safePage * 6, safePage * 6 + 6);
  const allPositions = [focusPosition, ...records.flatMap(i => [i.planted, i.planned, i.resolved].filter((s): s is Source => !!s).map(s => s.position))];
  const min = Math.min(...allPositions), max = Math.max(min + 1, ...allPositions);
  const x = (position: number) => 170 + (position - min) / (max - min) * 470;
  const ticks = [...new Set(Array.from({ length: 6 }, (_, i) => Math.round(min + (max - min) * i / 5)))];
  return <>
    {rows.length ? <div className="overflow-x-auto">
      <svg role="group" aria-label="복선별 설치와 예정·실제 회수 타임라인" viewBox={`0 0 670 ${85 + rows.length * 80}`} className="w-full" style={{ minWidth: 500 }}>
        {ticks.map(tick => <g key={tick}>
          <line x1={x(tick)} x2={x(tick)} y1="35" y2={55 + rows.length * 80} stroke={border} />
          <text x={x(tick)} y="28" fill={muted} fontSize="11" textAnchor="middle">{tick}회차</text>
        </g>)}
        <line x1={x(focusPosition)} x2={x(focusPosition)} y1="35" y2={55 + rows.length * 80} stroke={primary} strokeDasharray="3 3" />
        <text x={x(focusPosition)} y="13" textAnchor="middle" fill={primary} fontSize="11">살펴보는 회차</text>
        {rows.map((item, i) => {
          const y = 75 + i * 80;
          const closure = item.disposition === 'intentional_unresolved' || item.disposition === 'side_story';
          return <g key={item.id}>
            <title>{`${item.label} · 현재 등록 상태 ${item.registered_status}`}</title>
            <text x="4" y={y - 4} fill={ink} fontSize="12" fontWeight="600">{short(item.label, 12)}</text>
            <text x="4" y={y + 15} fill={muted} fontSize="11">{item.registered_status} · {item.disposition === 'side_story' ? '외전 이관' : item.disposition === 'intentional_unresolved' ? '의도적 미해결' : item.disposition === 'resolved' ? '해결' : '처분 미등록'}</text>
            {item.planted && item.planned && <path d={`M${x(item.planted.position)} ${y} V${y - 13} H${x(item.planned.position)}`} fill="none" stroke={primary} strokeDasharray="5 4" />}
            {item.planted && item.resolved && <path d={`M${x(item.planted.position)} ${y} V${y + 13} H${x(item.resolved.position)}`} fill="none" stroke={muted} strokeWidth="2" />}
            {([['planted', '설치', 0], ['planned', '예정 회수', -13], ['resolved', closure ? '처분 기록' : '실제 회수', 13]] as const).map(([key, label, delta]) => {
              const source = item[key];
              if (!source) return null;
              const px = x(source.position), py = y + delta;
              return <g key={key} role="button" tabIndex={0} aria-label={`${item.label}, ${label}, ${source.position}회차 ${source.title}${source.future ? ', 기준 회차 이후' : ''}`}
                onClick={() => onBrowse(source.id)} onKeyDown={e => activate(e, () => onBrowse(source.id))}
                className="cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">
                <title>{`${label}: ${source.position}. ${source.title}${source.future ? ' · 선택 회차 이후' : ''}`}</title>
                <circle cx={px} cy={py} r="12" fill="transparent" />
                {key === 'planted' ? <circle cx={px} cy={py} r="5" fill={muted} /> : key === 'planned'
                  ? <path d={`M${px} ${py - 7} l7 7 l-7 7 l-7 -7z`} fill={paper} stroke={primary} strokeWidth="2" />
                  : <rect x={px - 5} y={py - 5} width="10" height="10" fill={closure ? paper : muted} stroke={muted} strokeWidth="2" />}
              </g>;
            })}
            <text x="170" y={y + 37} fill={muted} fontSize="10">{[!item.planted && '설치 미등록', !item.planned && '계획 미정', !item.resolved && '회수·처분 회차 미등록'].filter(Boolean).join(' · ')}</text>
          </g>;
        })}
      </svg>
    </div> : <p className="py-10 text-center text-xs text-muted-foreground">등록된 복선이 없습니다. 복선을 등록하면 같은 회차 축에 표시됩니다.</p>}
    <p className="text-xs text-muted-foreground">● 설치 · ◇ 예정 회수(점선) · ■ 실제 회수 · □ 처분 기록 · 기호를 눌러 근거 살펴보기</p>
    <p className="mt-1 text-xs text-muted-foreground">현재 등록 상태이며 살펴보는 회차 당시의 상태와 다를 수 있습니다.</p>
    {records.length > 6 && <div className="mt-2 flex items-center justify-between text-xs">
      <Button size="sm" variant="ghost" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>복선 이전</Button>
      <span>{safePage * 6 + 1}–{safePage * 6 + rows.length} / 조회된 {records.length}개</span>
      <Button size="sm" variant="ghost" disabled={(safePage + 1) * 6 >= records.length} onClick={() => setPage(safePage + 1)}>복선 다음</Button>
    </div>}
  </>;
}

function EvidenceGraph({ pid, focus, view, onBrowse }: { pid: number; focus: StoryMapNode; view: 'relations' | 'foreshadows'; onBrowse: (id: number) => void }) {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ['story-map', pid, 'evidence', focus.id, view, offset],
    queryFn: ({ signal }) => api.get<Result>(`/projects/${pid}/story-map/evidence?chapter_id=${focus.id}&view=${view}&offset=${offset}`, { signal }),
    staleTime: 0,
  });
  return <>
    {query.isPending && <p role="status" className="py-10 text-center text-xs">그래프 자료를 불러오는 중…</p>}
    {query.isError && <p role="alert" className="py-4 text-xs">자료를 불러오지 못했습니다. {query.data && '마지막 조회 결과를 표시합니다.'}
      <Button size="sm" variant="ghost" onClick={() => void query.refetch()}>다시 불러오기</Button></p>}
    {query.data && <>
      {view === 'relations' ? <RelationNetwork key={offset} items={query.data.items} onBrowse={onBrowse} />
        : <ForeshadowTimeline key={offset} items={query.data.items} focusPosition={focus.position} onBrowse={onBrowse} />}
      <p className="mt-3 text-xs text-muted-foreground">기준: {focus.position}. {focus.title} · 조회 {query.data.items.length} / 전체 {query.data.total}개{query.isFetching ? ' · 갱신 중' : ''}</p>
      {query.data.total > 50 && <div className="mt-1 flex justify-between">
        <Button size="sm" variant="outline" disabled={query.data.offset === 0} onClick={() => setOffset(Math.max(0, query.data!.offset - 50))}>자료 이전 페이지</Button>
        <Button size="sm" variant="outline" disabled={query.data.next_offset === null} onClick={() => setOffset(query.data!.next_offset ?? 0)}>자료 다음 페이지</Button>
      </div>}
    </>}
  </>;
}

export function StoryVisualOverview({ pid, data, currentId, selectedId, onSelect, onBrowse, onManageCharacters }: {
  pid: number; data: StoryMapData; currentId: number | null; selectedId: number | null;
  onSelect: (id: number) => void; onBrowse: (id: number) => void;
  onManageCharacters?: () => void;
}) {
  const [mode, setMode] = useState<'workbench' | 'charts'>('workbench');
  const focus = data.nodes.find(n => n.id === selectedId) ?? data.nodes.find(n => n.id === data.anchor_id) ?? data.nodes[0];
  if (!focus) return null;
  return <div className="space-y-3">
    <div role="group" aria-label="스토리 지도 화면" className="story-view-tabs">
      <Button size="sm" variant={mode === 'workbench' ? 'secondary' : 'ghost'} aria-pressed={mode === 'workbench'} onClick={() => setMode('workbench')}>인물과 이야기 한눈에</Button>
      <Button size="sm" variant={mode === 'charts' ? 'secondary' : 'ghost'} aria-pressed={mode === 'charts'} onClick={() => setMode('charts')}>전체 흐름·복선 그래프</Button>
    </div>
    {mode === 'workbench' ? <StoryWorkbench key={`${pid}:${focus.id}`} pid={pid} map={data} focus={focus} currentId={currentId} onSelect={onSelect} onManageCharacters={onManageCharacters} /> : <>
    <Card title="전개 흐름도" description={`현재 범위 ${data.counts.total}회 중 ${data.nodes.length}회 표시 · 연결선은 회차 순서 · 점선 테두리는 기획 단계 · 노드를 눌러 상세 확인`}>
      <FlowGraph nodes={data.nodes} currentId={currentId} selectedId={selectedId} onSelect={onSelect} />
    </Card>
    <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 420px), 1fr))' }}>
      <Card title="인물 관계망" description="인물과 연결을 한곳에서 살펴보세요. 이름을 누르면 연결이 강조됩니다.">
        <EvidenceGraph key={`relations:${focus.id}`} pid={pid} focus={focus} view="relations" onBrowse={onBrowse} />
      </Card>
      <Card title="복선 타임라인" description="여러 복선의 설치와 예정·실제 회수를 같은 회차 축에서 비교합니다.">
        <EvidenceGraph key={`foreshadows:${focus.id}`} pid={pid} focus={focus} view="foreshadows" onBrowse={onBrowse} />
      </Card>
    </div>
    <Card title="회차별 집필량" description="현재 조회 페이지의 저장 글자 수입니다. 작성·확정 비율은 위 진행률에서 확인할 수 있습니다.">
      <WritingChart nodes={data.nodes} currentId={currentId} onSelect={onSelect} />
    </Card>
    </>}
  </div>;
}
