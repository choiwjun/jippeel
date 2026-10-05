import { useEffect, useId, useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, type ChapterGoalPayload } from '@/lib/api';
import type { StoryMapData, StoryMapNode } from '@/lib/storyMap';
import type { Evidence, Source } from './StoryMapEvidence';
import { Button } from '@/components/ui/button';
import './story-workbench.css';

interface Cast { id: number; name: string; role: string | null; mentioned: boolean; excerpt: string | null; scene_ids: number[]; event_ids: number[]; profile: Record<string, string | null> }
interface Scene { id: number; title: string; position: number; excerpt: string; character_ids: number[] }
interface Event { id: number; label: string; state_after: string | null; character_ids: number[]; foreshadow_ids: number[] }
interface Thread { id: string; label: string; registered_status: string | null; disposition: string | null; planted: Source | null; planned: Source | null; resolved: Source | null; character_ids: number[]; at_chapter: boolean }
export interface WorkbenchData {
  project_id: number; chapter_id: number; revision: number; summary: string | null; summary_id: number | null;
  characters: Cast[]; scenes: Scene[]; events: Event[]; relations: Evidence[]; foreshadows: Thread[];
  lore: { id: number; title: string; category: string | null; excerpt: string }[]; ambiguous_terms: string[];
}
const color = (id: number) => `var(--sw-person-${Math.abs(id) % 6})`;
const cut = (s: string, n = 15) => s.length > n ? s.slice(0, n) + '…' : s;
function DeskIcon({ kind }: { kind: 'cast' | 'network' | 'event' | 'thread' | 'scene' }) {
  const paths = {
    cast: <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a6 6 0 0112 0v2M16 5a3 3 0 010 6M18 14a5 5 0 013 4v2" /></>,
    network: <><circle cx="12" cy="5" r="3" /><circle cx="5" cy="19" r="3" /><circle cx="19" cy="19" r="3" /><path d="M10.5 8L6.5 16M13.5 8l4 8M8 19h8" /></>,
    event: <path d="M13 2L4 14h7l-1 8 10-13h-7z" />,
    thread: <><path d="M5 4h14v16H5zM8 8h8M8 12h5M8 16h3" /><path d="M16 3v5l2-1 2 1V3" /></>,
    scene: <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="M8 5v14M16 5v14M3 10h5M16 14h5" /></>,
  };
  return <span className={`sw-section-icon sw-icon-${kind}`} aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[kind]}</svg></span>;
}
function Avatar({ person, small = false }: { person: Cast; small?: boolean }) {
  return <span className={`sw-avatar ${small ? 'sw-avatar-small' : ''}`} style={{ '--person-color': color(person.id) } as React.CSSProperties} aria-hidden="true">{person.name.slice(0, 1)}</span>;
}
const intersects = (ids: number[], selected: number[]) => !selected.length || ids.some(id => selected.includes(id));
const goalFields: [keyof ChapterGoalPayload, string][] = [
  ['emotion_goal', '감정 목표'], ['core_events', '핵심 사건'], ['character_choices', '인물 선택'],
  ['cost', '대가'], ['prohibitions', '금지 사항'], ['next_hook', '다음 전개'],
  ['ending_intent', '결말 의도'], ['scene_type', '장면 유형'], ['target_chars_novelpia', '목표 글자 수'],
];
const profileFields = [['personality', '성격'], ['background', '배경'], ['appearance', '외모'], ['speech_style', '말투'], ['lifecycle_note', '상태 메모']];

function CastNetwork({ data, selected, onSelect }: { data: WorkbenchData; selected: number[]; onSelect: (ids: number[]) => void }) {
  const arrow = useId().replace(/:/g, '');
  const [mode, setMode] = useState<'relation' | 'relationship_change'>('relation');
  const [page, setPage] = useState(0);
  const cast = new Map(data.characters.map(c => [c.id, c]));
  const seeds = selected.length ? selected : data.characters.filter(c => c.mentioned || c.scene_ids.length || c.event_ids.length).map(c => c.id);
  const candidates = data.relations.filter(r => r.kind === mode && r.from_id != null && r.to_id != null && cast.has(r.from_id) && cast.has(r.to_id)
    && (seeds.includes(r.from_id) || seeds.includes(r.to_id)));
  const pairs = new Map<string, Evidence[]>();
  candidates.forEach(r => { const key = `${r.from_id}:${r.to_id}`; pairs.set(key, [...(pairs.get(key) ?? []), r]); });
  const grouped = [...pairs.values()];
  const safePage = Math.min(page, Math.max(0, Math.ceil(grouped.length / 6) - 1));
  const edges = grouped.slice(safePage * 6, safePage * 6 + 6);
  const visibleIds = [...new Set([...seeds.slice(0, 8), ...edges.flatMap(g => [g[0].from_id!, g[0].to_id!])])].filter(id => cast.has(id));
  const center = selected.length === 1 ? selected[0] : null;
  const outer = visibleIds.filter(id => id !== center);
  const points = new Map(outer.map((id, i) => {
    const angle = 2 * Math.PI * i / Math.max(outer.length, 1) - Math.PI / 2;
    return [id, { x: 320 + 210 * Math.cos(angle), y: 200 + 125 * Math.sin(angle) }];
  }));
  if (center !== null && cast.has(center)) points.set(center, { x: 320, y: 200 });
  return <>
    <div className="sw-row sw-between"><h3><DeskIcon kind="network" />누가 누구와 얽혀 있나요?</h3><div className="sw-segment">
      <button aria-pressed={mode === 'relation'} onClick={() => { setMode('relation'); setPage(0); }}>관계 설정</button>
      <button aria-pressed={mode === 'relationship_change'} onClick={() => { setMode('relationship_change'); setPage(0); }}>승인된 변화</button>
    </div></div>
    <p className="sw-help">{mode === 'relation' ? '현재 작가 설정 · 과거 시점의 관계를 뜻하지 않음' : '이 회차까지 승인된 변화 기록 · 최종 관계 상태와 구분'}</p>
    {visibleIds.length ? <div className="sw-network">
      <svg viewBox="0 0 640 400" role="group" aria-label="선택 인물과 직접 연결된 관계">
        <defs><marker id={arrow} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="currentColor" /></marker></defs>
        {edges.map((group, i) => {
          const e = group[0], a = points.get(e.from_id!)!, b = points.get(e.to_id!)!;
          const same = e.from_id === e.to_id, bend = i % 2 ? 30 : -25;
          const cx = (a.x + b.x) / 2 + bend, cy = (a.y + b.y) / 2 + bend;
          const length = Math.hypot(b.x - cx, b.y - cy) || 1;
          const endX = b.x - (b.x - cx) / length * 34, endY = b.y - (b.y - cy) / length * 34;
          const label = cut(group.length > 1 ? `${e.label} 외 ${group.length - 1}개 기록` : e.label, 15);
          const labelX = same ? a.x : (a.x + 2 * cx + b.x) / 4;
          const labelY = same ? a.y - 72 : (a.y + 2 * cy + b.y) / 4 - 8;
          const labelWidth = label.length * 11 + 18;
          return <g key={e.id}>
            <path d={same ? `M${a.x + 20} ${a.y - 20} C${a.x + 80} ${a.y - 100} ${a.x - 80} ${a.y - 100} ${a.x - 22} ${a.y - 25}` : `M${a.x} ${a.y}Q${cx} ${cy} ${endX} ${endY}`}
              fill="none" stroke="currentColor" strokeWidth="1.8" strokeDasharray={mode === 'relation' ? '5 5' : undefined} markerEnd={`url(#${arrow})`} />
            <rect x={labelX - labelWidth / 2} y={labelY - 15} width={labelWidth} height="24" rx="12" className="sw-edge-pill" />
            <text x={labelX} y={labelY + 1} textAnchor="middle" className="sw-edge-label">{label}</text>
          </g>;
        })}
        {[...points].map(([id, p]) => {
          const person = cast.get(id)!;
          return <g key={id} role="button" tabIndex={0} aria-pressed={selected.includes(id)} aria-label={`${person.name}, ${person.role || '역할 미등록'}, 인물 ${id} 선택`}
            className="sw-person-node" onClick={() => onSelect([id])} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect([id]); } }}>
            <title>{`${person.name} · ${person.role || '역할 미등록'} · 인물 #${id}`}</title>
            <circle cx={p.x} cy={p.y} r={selected.includes(id) ? 40 : 33} fill={`color-mix(in srgb, ${color(id)} 10%, var(--sw-paper))`} stroke={color(id)} strokeOpacity={selected.includes(id) ? 1 : .2} strokeWidth={selected.includes(id) ? 2 : 1} />
            <circle cx={p.x} cy={p.y} r="27" fill="none" stroke={color(id)} strokeOpacity=".4" strokeWidth="1" />
            <text x={p.x} y={p.y + 6} textAnchor="middle" fill={color(id)} fontSize="19" fontWeight="700">{person.name.slice(0, 1)}</text>
            <text x={p.x} y={p.y + 52} textAnchor="middle" className="sw-node-name">{cut(person.name, 10)}</text>
            <text x={p.x} y={p.y + 69} textAnchor="middle" className="sw-node-role">{person.role || '역할 미등록'}{person.event_ids.length ? ' · 승인 사건 연결' : person.mentioned ? ' · 원고 언급' : ''}</text>
          </g>;
        })}
      </svg>
    </div> : <div className="sw-empty">연결된 관계 기록이 없습니다. 인물 카드에서 관계를 등록할 수 있습니다.</div>}
    <p className="sw-help">선택 범위 {seeds.length}명 중 {Math.min(seeds.length, 8)}명과 현재 표시 연결의 상대를 그림에 표시합니다.</p>
    <details className="sw-details"><summary>관계의 내용과 근거 {candidates.length}개 보기</summary>
      <ul className="sw-records">{edges.flat().map(e => <li key={e.id}>
        <b>{e.from_name} → {e.to_name}</b><span>{e.label}</span><p>{e.excerpt}</p><small>{e.source ? `${e.source.position}회차 · ${e.source.title} · 원고 v${e.source.revision}` : '시점 없는 현재 설정'}</small>
      </li>)}</ul>
      {data.relations.some(e => e.kind === mode && (e.from_id == null || e.to_id == null)) && <p className="sw-help">인물 ID가 없는 이름 기반 기록은 전체 그래프의 별도 노드에서 확인할 수 있습니다.</p>}
    </details>
    {grouped.length > 6 && <div className="sw-row sw-between sw-help"><button disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>← 이전 연결</button><span>{safePage * 6 + 1}–{Math.min(grouped.length, safePage * 6 + 6)} / {grouped.length}쌍</span><button disabled={(safePage + 1) * 6 >= grouped.length} onClick={() => setPage(safePage + 1)}>다음 연결 →</button></div>}
  </>;
}

function Workspace({ pid, data, map, focus, currentId, onSelect, onManageCharacters }: { pid: number; data: WorkbenchData; map: StoryMapData; focus: StoryMapNode; currentId: number | null; onSelect: (id: number) => void; onManageCharacters?: () => void }) {
  const relevant = data.characters.filter(c => c.mentioned || c.scene_ids.length || c.event_ids.length);
  const [selected, setSelected] = useState<number[]>([]);
  const [search, setSearch] = useState('');
  const [allCast, setAllCast] = useState(false);
  const [combine, setCombine] = useState(false);
  const [castPage, setCastPage] = useState(0);
  const [selectedScene, setSelectedScene] = useState<number | null>(null);
  const [threadAll, setThreadAll] = useState(false);
  const [threadPage, setThreadPage] = useState(0);
  const [scenePage, setScenePage] = useState(0);
  const [eventPage, setEventPage] = useState(0);
  const validSelected = selected.filter(id => data.characters.some(c => c.id === id));
  const choose = (ids: number[]) => { setSelected(ids); setSelectedScene(null); setEventPage(0); setThreadPage(0); };
  const castById = new Map(data.characters.map(c => [c.id, c]));
  const names = (ids: number[]) => ids.map(id => castById.get(id)?.name || `인물 #${id}`).join(' + ');
  const castRows = (allCast || search.trim() ? data.characters : relevant).filter(c => `${c.name} ${c.role ?? ''}`.toLowerCase().includes(search.trim().toLowerCase()));
  const cp = Math.min(castPage, Math.max(0, Math.ceil(castRows.length / 10) - 1));
  const sceneRows = data.scenes;
  const sp = Math.min(scenePage, Math.max(0, Math.ceil(sceneRows.length / 6) - 1));
  const events = data.events.filter(e => intersects(e.character_ids, validSelected));
  const ep = Math.min(eventPage, Math.max(0, Math.ceil(events.length / 5) - 1));
  const threads = data.foreshadows.filter(f => threadAll || (validSelected.length ? intersects(f.character_ids, validSelected) : f.at_chapter));
  const tp = Math.min(threadPage, Math.max(0, Math.ceil(threads.length / 4) - 1));
  const at = map.nodes.findIndex(n => n.id === focus.id), previous = map.nodes[at - 1], next = map.nodes[at + 1];
  const goal = focus.goal;
  const pages = (page: number, total: number, size: number, set: (value: number) => void, label: string) => total > size && <div className="sw-row sw-between sw-help">
    <button aria-label={`${label} 이전`} disabled={page === 0} onClick={() => set(page - 1)}>← 이전</button><span>{page * size + 1}–{Math.min(total, (page + 1) * size)} / {total}</span><button aria-label={`${label} 다음`} disabled={(page + 1) * size >= total} onClick={() => set(page + 1)}>다음 →</button>
  </div>;
  return <div className="story-workbench">
    <header className="sw-hero">
      <div className="sw-chapter-mark" aria-hidden="true"><small>CHAPTER</small><b>{String(focus.position).padStart(2, '0')}</b></div>
      <div className="sw-hero-copy"><div className="sw-eyebrow">{focus.id === currentId ? '지금 쓰는 이야기' : '살펴보는 이야기'}<span>STORY DESK</span></div><h2><small>{focus.position}회차</small><span>{focus.title || '제목 없음'}</span></h2>
        <p>{data.summary ? cut(data.summary, 110) : '이 회차의 승인된 줄거리 요약은 아직 없습니다.'}</p></div>
      <div className="sw-status"><span>{focus.id === currentId ? '● 현재 집필' : '○ 탐색 중'}</span><small>저장 원고 v{data.revision} 기준</small><small>{focus.word_count.toLocaleString()}자 · {data.scenes.length}개 장면</small></div>
    </header>
    <div className="sw-journey" aria-label="이전 회차부터 다음 계획까지">
      <button disabled={!previous} onClick={() => previous && onSelect(previous.id)}><small>01 · 이전 회차</small><strong>{previous ? `${previous.position}. ${previous.title}` : '현재 조회 범위의 시작'}</strong><span>{previous ? `저장 ${previous.word_count.toLocaleString()}자 · 회차 순서로 연결` : '이전 범위는 지도 범위/페이지에서 탐색'}</span></button>
      <div className="sw-journey-current"><small>02 · 이번 회차 목표 <em>작가 계획</em></small><strong>{goal?.core_events?.[0] || goal?.emotion_goal || '목표 미등록'}</strong><span>{goal?.character_choices?.[0] || goal?.cost || '인물의 선택과 대가를 목표에 기록해 보세요.'}</span></div>
      <button disabled={!next} onClick={() => next && onSelect(next.id)}><small>03 · 다음 전개 <em>작가 계획</em></small><strong>{next?.goal?.core_events?.[0] || next?.goal?.emotion_goal || '다음 목표 미등록'}</strong><span>{next ? `${next.position}. ${next.title}` : '다음 범위는 지도 범위/페이지에서 탐색'}</span></button>
    </div>
    <div className="sw-selection"><span>{validSelected.length ? <><b>{names(validSelected)}</b> 중심으로 연결 보는 중</> : <><b>이번 회차 전체</b> · 인물이나 장면 조합을 선택해 보세요</>}</span>
      {validSelected.length > 1 && <small>선택 인물 중 한 명 이상과 연결된 자료</small>}
      {validSelected.length > 0 && <button onClick={() => choose([])}>선택 해제 ×</button>}</div>
    <div className="sw-layout">
      <aside className="sw-cast sw-surface" aria-label="인물 선택">
        <div className="sw-row sw-between"><h3><DeskIcon kind="cast" />이야기 속 인물</h3><span className="sw-count">{data.characters.length}</span></div>
        <input className="sw-search" aria-label="인물 이름이나 역할 검색" placeholder="이름·역할 검색" value={search} onChange={e => { setSearch(e.target.value); setCastPage(0); }} />
        <div className="sw-segment"><button aria-pressed={!allCast} onClick={() => { setAllCast(false); setCastPage(0); }}>이번 회차 {relevant.length}</button><button aria-pressed={allCast} onClick={() => { setAllCast(true); setCastPage(0); }}>전체 {data.characters.length}</button></div>
        <label className="sw-help sw-row"><input type="checkbox" checked={combine} onChange={e => setCombine(e.target.checked)} />여러 인물 조합해서 보기</label>
        <div className="sw-cast-list">{castRows.slice(cp * 10, cp * 10 + 10).map(c => <button key={c.id} className="sw-cast-button" style={{ '--person-color': color(c.id) } as React.CSSProperties} aria-pressed={validSelected.includes(c.id)} onClick={() => choose(combine ? validSelected.includes(c.id) ? validSelected.filter(id => id !== c.id) : [...validSelected, c.id] : [c.id])}>
          <Avatar person={c} /><span><b>{c.name}<em>{c.role || '역할 미등록'}</em></b><small>{c.event_ids.length ? '승인 사건 연결' : c.mentioned ? '원고 언급 후보' : c.scene_ids.length ? '장면 초안 언급' : '작품 등록 인물'}</small></span><span aria-hidden="true">›</span>
        </button>)}</div>
        {!castRows.length && <p className="sw-empty">해당 인물이 없습니다. 전체 인물도 확인해 보세요.</p>}
        {pages(cp, castRows.length, 10, setCastPage, '인물')}
        <p className="sw-help">이름 언급은 회상·인용을 포함할 수 있어 실제 등장을 확정하지 않습니다.</p>
        {onManageCharacters ? <button className="sw-link" onClick={onManageCharacters}>인물 카드 관리 ↗</button> : <Link className="sw-link" to={`/projects/${pid}/characters`}>인물 카드 관리 ↗</Link>}
      </aside>
      <section className="sw-surface sw-main"><CastNetwork key={validSelected.join(',')} data={data} selected={validSelected} onSelect={choose} /></section>
      <aside className="sw-surface sw-context" aria-label="인물과 연결된 사건·복선">
        <div className="sw-row sw-between"><h3><DeskIcon kind="event" />현재 얽힌 사건</h3><span className="sw-count">{events.length}</span></div>
        <p className="sw-help">이 회차의 승인 기록 · 원고 근거 일치</p>
        <div className="sw-event-list">{events.slice(ep * 5, ep * 5 + 5).map((e, i) => <details key={e.id} className="sw-event" open={events.length === 1}>
          <summary><span className="sw-event-index" aria-hidden="true">{String(ep * 5 + i + 1).padStart(2, '0')}</span>{e.label}</summary><p>{e.state_after || '변화 내용 미등록'}</p><small>{e.character_ids.length ? names(e.character_ids) : '인물 ID 연결 미등록'}</small>
        </details>)}</div>
        {!events.length && <p className="sw-empty">이 선택에 연결된 승인 사건이 없습니다.</p>}
        {pages(ep, events.length, 5, setEventPage, '사건')}
        <div className="sw-row sw-between sw-top-border"><h3><DeskIcon kind="thread" />이어지는 복선</h3><button className="sw-link" onClick={() => { setThreadAll(!threadAll); setThreadPage(0); }}>{threadAll ? '선택과 연결된 복선' : '작품 전체 보기'}</button></div>
        <p className="sw-help">{validSelected.length && !threadAll ? '같은 승인 사건에 기록된 복선' : threadAll ? '작품 전체의 현재 등록 상태' : '이 회차에 설치·회수·계획이 연결된 복선'}</p>
        {threads.slice(tp * 4, tp * 4 + 4).map(f => <article className="sw-thread" key={f.id} data-resolved={f.disposition === 'resolved'}>
          <div className="sw-row sw-between"><b>{f.label}</b><small className="sw-thread-status">{f.registered_status || '상태 미등록'}</small></div>
          <div className="sw-thread-track"><span>설치 <b>{f.planted ? `${f.planted.position}회` : '미등록'}</b></span><i>→</i><span className="sw-plan">예정 <b>{f.planned ? `${f.planned.position}회` : '미정'}</b></span><i>→</i><span>{f.disposition === 'intentional_unresolved' || f.disposition === 'side_story' ? '처분' : '회수'} <b>{f.resolved ? `${f.resolved.position}회` : '미등록'}</b></span></div>
          {f.disposition === 'intentional_unresolved' || f.disposition === 'side_story' ? <small>{f.disposition === 'side_story' ? '외전 이관' : '의도적 미해결'}</small> : null}
        </article>)}
        {!threads.length && <p className="sw-empty">등록된 연결이 없습니다. 작품 전체 복선은 따로 볼 수 있습니다.</p>}
        {pages(tp, threads.length, 4, setThreadPage, '복선')}
      </aside>
    </div>
    <section className="sw-surface sw-scenes" aria-label="장면 흐름과 인물 조합">
      <div className="sw-row sw-between"><div><h3><DeskIcon kind="scene" />장면을 따라 인물 조합 보기</h3><p className="sw-help">장면 순서 → · 같은 초안에서 이름이 함께 언급된 후보 · 원고 반영 여부와 실제 동행은 미확정</p></div><span className="sw-count">{data.scenes.length}개 장면</span></div>
      <div className="sw-scene-grid">{sceneRows.slice(sp * 6, sp * 6 + 6).map(s => <button className={`sw-scene ${validSelected.length && !intersects(s.character_ids, validSelected) ? 'sw-dim' : ''}`} key={s.id}
        aria-pressed={selectedScene === s.id} onClick={() => { setSelected(s.character_ids); setSelectedScene(s.id); setEventPage(0); setThreadPage(0); }}>
        <div className="sw-scene-number"><small>SCENE</small><b>{String(s.position).padStart(2, '0')}</b><span aria-hidden="true">↗</span></div><strong>{s.title || '제목 없는 장면'}</strong><p>{cut(s.excerpt, 100) || '내용 미등록'}</p>
        <div className="sw-row sw-wrap">{s.character_ids.map(id => castById.get(id)).filter((c): c is Cast => !!c).map(c => <span className="sw-person-chip" key={c.id}><Avatar person={c} small />{c.name}</span>)}</div>
        {!s.character_ids.length && <span className="sw-help">인물 언급 매칭 없음</span>}
      </button>)}</div>
      {!sceneRows.length && <p className="sw-empty">장면을 나누어 기록하면 전개 순서와 인물 조합을 함께 볼 수 있습니다.</p>}
      {pages(sp, sceneRows.length, 6, setScenePage, '장면')}
      {selectedScene !== null && <details className="sw-details" open><summary>선택한 장면의 근거 발췌</summary><p className="sw-excerpt">{data.scenes.find(s => s.id === selectedScene)?.excerpt}</p></details>}
    </section>
    <div className="sw-details-grid">
      <details className="sw-surface sw-details"><summary>선택 인물의 성격·배경·말투</summary><p className="sw-help">현재 인물 카드 설정 · 회차별 과거 상태와 구분</p>
        {!validSelected.length && <p>살펴볼 인물을 선택해 주세요.</p>}
        {data.characters.filter(c => validSelected.includes(c.id)).map(c => <div className="sw-record" key={c.id}><b>{c.name}</b>
          {profileFields.map(([key, label]) => <p className="sw-excerpt" key={key}>{label}: {c.profile[key] || '미등록'}</p>)}
        </div>)}
      </details>
      <details className="sw-surface sw-details"><summary>선택 인물의 원고 언급 근거</summary>{data.characters.filter(c => (!validSelected.length || validSelected.includes(c.id)) && c.excerpt).map(c => <div className="sw-record" key={c.id}><b>{c.name}</b><p className="sw-excerpt">{c.excerpt}</p></div>)}
        {data.ambiguous_terms.length > 0 && <p className="sw-help">여러 인물이 공유해 자동 배정하지 않은 이름/별칭: {data.ambiguous_terms.join(', ')}</p>}
      </details>
      <details className="sw-surface sw-details"><summary>관련 장소·세계관 {data.lore.length}개</summary><p className="sw-help">현재 원고의 제목·키워드 일치 후보입니다. 실제 장소나 사건 발생을 확정하지 않습니다.</p>{data.lore.map(l => <div className="sw-record" key={l.id}><b>{l.category} · {l.title}</b><p>{l.excerpt}</p></div>)}</details>
      <details className="sw-surface sw-details"><summary>승인 요약과 이번 목표 전체</summary><p className="sw-help">승인 요약</p><p className="sw-excerpt">{data.summary || '승인되고 현재 원문과 일치하는 요약이 없습니다.'}</p><p className="sw-help">작가 계획</p>
        {goalFields.map(([key, label]) => <div className="sw-record" key={key}><b>{label}</b><p className="sw-excerpt">{Array.isArray(goal?.[key]) ? (goal[key] as string[]).join('\n') || '미등록' : String(goal?.[key] ?? '미등록')}</p></div>)}
      </details>
    </div>
  </div>;
}

export function StoryWorkbench({ pid, map, focus, currentId, onSelect, onManageCharacters }: { pid: number; map: StoryMapData; focus: StoryMapNode; currentId: number | null; onSelect: (id: number) => void; onManageCharacters?: () => void }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['story-map', pid, 'workbench', focus.id, focus.revision],
    queryFn: ({ signal }) => api.get<WorkbenchData>(`/projects/${pid}/story-map/workbench?chapter_id=${focus.id}`, { signal }), staleTime: 0, placeholderData: keepPreviousData });
  const mismatch = !!query.data && query.data.revision !== focus.revision;
  // A concurrent save can make the independently fetched map older than this response.
  useEffect(() => {
    if (mismatch && !query.isPlaceholderData) void client.invalidateQueries({ queryKey: ['story-map', pid] });
  }, [client, pid, focus.revision, query.data?.revision, query.isPlaceholderData, mismatch]);
  return <>
    {query.isPending && <div className="sw-loading" role="status">이 회차의 인물·장면·사건을 연결하는 중…</div>}
    {query.isError && <div className="sw-loading" role="alert">집필 보드를 불러오지 못했습니다. {query.data && '마지막 조회 자료를 표시합니다.'}<Button variant="outline" onClick={() => void query.refetch()}>다시 불러오기</Button></div>}
    {mismatch && <div className="sw-loading" role="status">원고와 연결 자료의 버전을 맞추는 중입니다.<Button variant="outline" onClick={() => void client.invalidateQueries({ queryKey: ['story-map', pid] })}>다시 불러오기</Button></div>}
    {query.data && <div hidden={mismatch}><p className="mb-2 text-xs text-muted-foreground">{query.isFetching ? '새 저장본의 연결을 갱신하는 중…' : `연결 자료: 저장 원고 v${query.data.revision} 기준`}</p><Workspace key={`${pid}:${focus.id}`} pid={pid} data={query.data} map={map} focus={focus} currentId={currentId} onSelect={onSelect} onManageCharacters={onManageCharacters} /></div>}
  </>;
}
