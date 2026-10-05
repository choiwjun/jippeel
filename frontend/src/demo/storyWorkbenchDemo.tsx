// Standalone, read-only synthetic sample. No application API or persisted state.
import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { StoryVisualOverview } from '@/components/editor/StoryVisualOverview';
import type { WorkbenchData } from '@/components/editor/StoryWorkbench';
import type { Evidence, Source } from '@/components/editor/StoryMapEvidence';
import type { StoryMapData, StoryMapNode } from '@/lib/storyMap';
import '@/index.css';

const titles = ['사라진 초대장', '안개 속의 거래', '왕립 도서관의 비밀', '갈라지는 동맹', '붉은 탑의 증언', '배신자의 선택', '마지막 봉인', '안개가 걷힌 도시'];
const goals = ['초대장에 숨은 암호를 발견한다', '정보상과 거래하고 대가를 약속한다', '금지된 기록에서 왕실의 비밀을 발견한다', '동료의 진심을 의심하고 동맹이 갈라진다', '붉은 탑에서 사라진 증인을 찾는다', '이안이 왕실을 등지고 서하를 선택한다', '초대장으로 도시의 봉인을 해제한다', '선택의 대가와 새로운 질서를 보여준다'];
const nodes: StoryMapNode[] = titles.map((title, i) => ({
  id: i + 1, position: i + 1, volume: 1, title, flow_stage: i < 2 ? 'confirmed' : i === 2 ? 'writing' : 'planning',
  word_count: [5200, 4850, 3100, 0, 0, 0, 0, 0][i], revision: i < 3 ? 3 : 1,
  goal: { core_events: [goals[i]], ...(i === 2 ? {
    emotion_goal: '호기심이 불신으로 변한다', character_choices: ['서하는 이안을 믿고 금지 구역에 들어간다'],
    cost: '레온에게 정체를 들키고 도서관 출입권을 잃는다', prohibitions: ['왕실의 최종 목적은 아직 밝히지 않는다'],
    next_hook: '도윤이 건넨 쪽지에는 이안의 이름이 적혀 있다', ending_intent: '동맹에 대한 첫 의심', scene_type: '탐색 → 발견 → 대치', target_chars_novelpia: 5000,
  } : {}) }, goal_version: 1, goal_base_revision: i < 3 ? 3 : 1, scene_count: i === 2 ? 3 : 0,
}));
const ref = (id: number): Source => ({ id, title: titles[id - 1], position: id, revision: nodes[id - 1].revision, future: id > 3 });
function evidence(partial: Pick<Evidence, 'id' | 'kind' | 'label'> & Partial<Evidence>): Evidence {
  return { excerpt: '', basis: '체험용 예시', source: null, from_name: null, to_name: null, planned: null, review_key: null,
    evidence_token: null, review_text: null, latest_decision: null, planted: null, resolved: null, registered_status: null,
    source_revision: null, visibility: null, disposition: null, ...partial };
}
const people = [
  { id: 1, name: '서하', role: '주인공', personality: '의심이 많지만 한번 믿으면 끝까지 지킨다', background: '실종된 오빠의 흔적을 쫓는 기록 복원가', speech_style: '짧고 분명하게 묻는다' },
  { id: 2, name: '이안', role: '동료', personality: '여유로운 태도로 진심을 숨긴다', background: '왕실의 비밀을 알고 있는 전직 근위병', speech_style: '농담 속에 경고를 섞는다' },
  { id: 3, name: '레온', role: '대립 인물', personality: '질서와 책임을 진실보다 앞세운다', background: '금지된 기록을 지키는 왕실 감찰관', speech_style: '질문 대신 명령한다' },
  { id: 4, name: '미라', role: '정보상', personality: '누구에게나 친절하지만 대가는 잊지 않는다', background: '도시 곳곳의 소문을 거래한다', speech_style: '가격을 말하듯 사람을 떠본다' },
  { id: 5, name: '도윤', role: '조력자', personality: '조심스럽고 관찰력이 좋다', background: '서하와 함께 자란 도서관 사서', speech_style: '말보다 메모로 마음을 전한다' },
];
const scenes = [
  { id: 31, position: 1, title: '금지 서고에 들어가다', excerpt: '서하는 이안이 건넨 열쇠로 금지 서고의 문을 열었다. “이번 한 번만 믿을게.” 어둠 속에서 이안의 왼손 흉터가 희미하게 빛났다.', character_ids: [1, 2] },
  { id: 32, position: 2, title: '장부의 빈칸과 경고', excerpt: '도윤은 서하에게 찢어진 거래 장부를 내밀었다. “미라가 찾던 건 돈의 흐름이 아니었어.” 복원된 페이지에는 왕실의 문장과 실종된 오빠의 이름이 나란히 찍혀 있었다.', character_ids: [1, 4, 5] },
  { id: 33, position: 3, title: '피할 수 없는 대치', excerpt: '레온이 출구를 막았다. 이안은 서하의 앞을 가로섰다. “네가 지키려는 건 왕실이야, 아니면 그 사람의 비밀이야?” 레온의 손이 검에서 멈췄다.', character_ids: [1, 2, 3] },
];
const events = [
  { id: 101, label: '거래 장부에서 실종자의 이름 발견', state_after: '서하는 오빠의 실종과 왕실이 연결되어 있음을 알게 된다. 도윤은 장부를 넘기고 조사에 합류한다.', character_ids: [1, 5], foreshadow_ids: [3] },
  { id: 102, label: '이안이 레온을 막고 서하를 보호', state_after: '서하와 이안의 신뢰가 깊어진다. 레온은 이안을 왕실의 배신자로 의심하기 시작한다.', character_ids: [1, 2, 3], foreshadow_ids: [4] },
];
const relations = [
  [1, 2, '불안한 동맹', '서하는 이안의 도움을 받지만 그가 숨기는 과거를 의심한다.'],
  [1, 3, '추적과 대립', '레온은 금지 기록을 열람한 서하를 추적한다.'],
  [2, 4, '정보 거래', '미라는 이안의 옛 신분을 대가로 왕실 정보를 넘긴다.'],
  [3, 4, '숨겨진 약속', '미라는 레온에게도 정보를 제공하고 있다.'],
  [1, 5, '오랜 신뢰', '도윤은 서하의 과거를 아는 유일한 친구다.'],
].map(([from, to, label, excerpt], i) => evidence({ id: `relation-${i}`, kind: 'relation', from_id: Number(from), to_id: Number(to),
  from_name: people[Number(from) - 1].name, to_name: people[Number(to) - 1].name, label: String(label), excerpt: String(excerpt), basis: '현재 작가 설정' }));
relations.push(evidence({ id: 'change-102', kind: 'relationship_change', label: '의심 속에서 신뢰가 깊어짐', excerpt: '이안이 레온을 막고 서하를 보호한다.', from_id: 1, to_id: 2, from_name: '서하', to_name: '이안', source: ref(3), source_revision: 3, visibility: 'approved', basis: '예시 승인 사건' }));
const foreshadows = [
  evidence({ id: 'foreshadow-1', kind: 'foreshadow', label: '붉은 초대장', planted: ref(1), planned: ref(7), registered_status: '설치' }),
  evidence({ id: 'foreshadow-2', kind: 'foreshadow', label: '왕실의 문장', planted: ref(2), planned: ref(5), registered_status: '설치' }),
  evidence({ id: 'foreshadow-3', kind: 'foreshadow', label: '찢어진 거래 장부', planted: ref(1), planned: ref(3), resolved: ref(3), registered_status: '회수', disposition: 'resolved' }),
  evidence({ id: 'foreshadow-4', kind: 'foreshadow', label: '이안의 왼손 흉터', planted: ref(3), planned: ref(6), registered_status: '설치' }),
  evidence({ id: 'foreshadow-5', kind: 'foreshadow', label: '도시 아래의 종소리', planted: ref(2), registered_status: '보류' }),
];
// Components read the seeded cache only. Retries/focus refetches are disabled.
const client = new QueryClient({ defaultOptions: { queries: { enabled: false, retry: false, refetchOnWindowFocus: false } } });
for (const node of nodes) {
  const current = node.id === 3;
  const workbench: WorkbenchData = {
    project_id: 1, chapter_id: node.id, revision: node.revision, summary_id: current ? 201 : null,
    summary: current ? '서하와 이안은 금지 서고에서 오빠의 실종과 왕실을 잇는 기록을 발견한다. 도윤의 도움으로 장부의 비밀을 풀지만, 출구에서 레온과 마주친다.' : null,
    characters: people.map(p => ({ id: p.id, name: p.name, role: p.role, mentioned: current,
      excerpt: current ? scenes.find(s => s.character_ids.includes(p.id))?.excerpt ?? null : null,
      scene_ids: current ? scenes.filter(s => s.character_ids.includes(p.id)).map(s => s.id) : [],
      event_ids: current ? events.filter(e => e.character_ids.includes(p.id)).map(e => e.id) : [],
      profile: { personality: p.personality, background: p.background, speech_style: p.speech_style, appearance: null, lifecycle_status: 'active', lifecycle_note: null } })),
    scenes: current ? scenes : [], events: current ? events : [], relations: relations.filter(r => !r.source || r.source.position <= node.position),
    foreshadows: foreshadows.map(f => ({ id: f.id, label: f.label, registered_status: f.registered_status, disposition: f.disposition,
      planted: f.planted, planned: f.planned, resolved: f.resolved,
      character_ids: current ? [...new Set(events.filter(e => e.foreshadow_ids.includes(Number(f.id.split('-')[1]))).flatMap(e => e.character_ids))] : [],
      at_chapter: [f.planted, f.planned, f.resolved].some(r => r?.id === node.id) })),
    lore: current ? [{ id: 1, title: '왕립 도서관', category: '장소', excerpt: '왕실의 역사를 보관하는 거대한 도서관. 금지 서고에는 지워진 가문의 기록이 남아 있다.' },
      { id: 2, title: '왕실의 문장', category: '설정', excerpt: '왕실 직속 거래에만 쓰이는 붉은 문장. 사라진 사람들의 기록에서 반복된다.' }] : [], ambiguous_terms: [],
  };
  client.setQueryData(['story-map', 1, 'workbench', node.id, node.revision], workbench);
  for (const [view, items] of [['relations', workbench.relations], ['foreshadows', foreshadows]] as const) {
    const atFocus = (source: Source | null) => source ? { ...source, future: source.position > node.position } : null;
    const focusedItems = items.map(item => ({ ...item, source: atFocus(item.source), planted: atFocus(item.planted), planned: atFocus(item.planned), resolved: atFocus(item.resolved) }));
    client.setQueryData(['story-map', 1, 'evidence', node.id, view, 0], { project_id: 1, chapter_id: node.id, chapter_revision: node.revision, view, total: items.length, offset: 0, next_offset: null, items: focusedItems });
  }
}
const map: StoryMapData = { project_id: 1, anchor_id: 3, scope: 'all', counts: { total: 8, written: 3, confirmed: 2 }, nodes,
  volumes: [{ volume: 1, first_chapter_id: 1, total: 8, written: 3, confirmed: 2 }], offset: 0, next_offset: null };
client.setQueryData(['story-map', 1, 'overview', 'all', null], map);
function Demo() {
  const [selected, setSelected] = useState(3);
  const [scope, setScope] = useState<'near' | 'all'>(() => new URLSearchParams(location.search).get('scope') === 'all' ? 'all' : 'near');
  const [light, setLight] = useState(true);
  const [notice, setNotice] = useState('');
  return <main className="story-demo-shell mx-auto max-w-[1480px] p-4 md:p-8">
    <header className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-xs font-semibold tracking-widest text-primary">JIPPEEL · STORY DESK</p><h1 className="mt-2 text-2xl font-semibold">이야기의 연결을 한눈에</h1>
        <p className="mt-2 text-sm text-muted-foreground">예시 작품 「안개도시의 초대장」 · 체험용 데이터 · 실제 원고 저장 없음</p></div>
      <button className="rounded-lg border border-border px-3 py-2 text-xs" onClick={() => { document.documentElement.classList.toggle('light', !light); setLight(!light); }}>{light ? '어두운 화면' : '밝은 화면'}</button>
    </header>
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-primary/10 px-4 py-3 text-xs">
      <span><b>인물 클릭</b> → 관련 연결 보기　 <b>장면 클릭</b> → 인물 조합 보기　 <b>작품 전체</b> → 모든 회차 보기</span>
      <button className="font-semibold text-primary underline underline-offset-2" onClick={() => { setSelected(3); setScope('near'); }}>3회차 예시로 돌아오기 ↗</button>
    </div>
    <div className="mb-4 flex gap-2" role="group" aria-label="예시 지도 범위">{([['near', '현재 주변'], ['all', '작품 전체']] as const).map(([value, label]) => <button className={`rounded-lg border px-3 py-2 text-xs ${scope === value ? 'border-primary bg-primary/10 text-primary' : 'border-border'}`} key={value} aria-pressed={scope === value} onClick={() => setScope(value)}>{label}</button>)}</div>
    {scope === 'near' && selected !== 3 && <p className="mb-3 text-xs text-muted-foreground">상세 예시는 3회차에 준비되어 있습니다. 다른 회차에서는 회차 이동과 전개 계획을 살펴보세요.</p>}
    {notice && <p role="status" className="mb-3 text-sm">{notice}<button className="ml-3 underline" onClick={() => setNotice('')}>닫기</button></p>}
    <StoryVisualOverview pid={1} data={{ ...map, scope }} currentId={3} selectedId={selected} onSelect={setSelected} onBrowse={id => { setSelected(id); setScope('near'); }}
      onManageCharacters={() => setNotice('체험 화면에서는 인물·장면·그래프 선택을 살펴볼 수 있습니다. 인물 편집은 실제 작품에서 이용해 주세요.')} />
    <footer className="mt-6 text-center text-xs text-muted-foreground">이 화면의 인물·사건·원고·승인 기록은 모두 기능 설명을 위한 가상 예시입니다.</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}><MemoryRouter><Demo /></MemoryRouter></QueryClientProvider>);
