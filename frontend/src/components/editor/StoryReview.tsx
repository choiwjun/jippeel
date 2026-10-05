import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';

export interface ReviewDecision {
  id: number; item_key: string; sequence: number; evidence_token: string;
  decision: 'adopt' | 'hold' | 'discard'; proposal: string; reason: string; created_at: string;
  snapshot_json: { label: string; basis: string; review_text?: string; excerpt: string };
}
export interface Reviewable {
  id: string; evidence_token: string; review_text: string;
  latest_decision: ReviewDecision | null;
}
interface ReviewDraft { base: Reviewable; proposal: string; reason: string }
const drafts = new Map<string, ReviewDraft>();
function readDraft(key: string, item: Reviewable): ReviewDraft {
  const cached = drafts.get(key);
  if (cached) return cached;
  try {
    const raw = sessionStorage.getItem(key);
    const data = raw ? JSON.parse(raw) as ReviewDraft : null;
    if (data && data.base?.id === item.id && typeof data.base.evidence_token === 'string' &&
        typeof data.base.review_text === 'string' && typeof data.proposal === 'string' && typeof data.reason === 'string') {
      drafts.set(key, data); return data;
    }
  } catch { /* Memory storage remains available when browser storage is blocked. */ }
  return { base: item, proposal: '', reason: '' };
}

const actions = { adopt: '검토안 채택', hold: '보류', discard: '폐기' };
function DecisionDetail({ row }: { row: ReviewDecision }) {
  return <div className="space-y-2">
    <p>{actions[row.decision]} · {new Date(row.created_at).toLocaleString('ko-KR')}</p>
    <p className="whitespace-pre-wrap break-words">이유: {row.reason}</p>
    <details>
      <summary className="cursor-pointer">당시 내용과 검토안 비교</summary>
      <div className="mt-2 grid gap-2 lg:grid-cols-2">
        <div><h5 className="font-semibold">당시 내용</h5><p className="max-h-64 overflow-auto whitespace-pre-wrap break-words">{row.snapshot_json.review_text || row.snapshot_json.excerpt}</p></div>
        <div><h5 className="font-semibold">작가 검토안</h5><p className="max-h-64 overflow-auto whitespace-pre-wrap break-words">{row.proposal || '작성하지 않음'}</p></div>
      </div>
    </details>
  </div>;
}

export function StoryReviewEditor({ pid, item }: { pid: number; item: Reviewable }) {
  const client = useQueryClient();
  // Freeze the reviewed basis until an explicit reload. Refetching never rebases typed work.
  const key = `jippeel:story-review-draft:v1:${pid}:${item.id}`;
  const [draft, setDraft] = useState(() => readDraft(key, item));
  const { base, proposal, reason } = draft;
  const [storageError, setStorageError] = useState(false);
  const changeDraft = (next: ReviewDraft) => {
    drafts.set(key, next);
    try { sessionStorage.setItem(key, JSON.stringify(next)); setStorageError(false); }
    catch { setStorageError(true); }
    setDraft(next);
  };
  const [saved, setSaved] = useState(false);
  const changed = base.evidence_token !== item.evidence_token ||
    (base.latest_decision?.id ?? null) !== (item.latest_decision?.id ?? null);
  const save = useMutation({
    mutationFn: ({ decision, submitted }: { decision: ReviewDecision['decision']; submitted: ReviewDraft }) => api.post<ReviewDecision>(`/projects/${pid}/story-map/review-decisions`, {
      item_key: submitted.base.id, evidence_token: submitted.base.evidence_token,
      expected_last_id: submitted.base.latest_decision?.id ?? null,
      decision, proposal: submitted.proposal, reason: submitted.reason,
    }),
    onSuccess: (_row, { submitted }) => {
      setSaved(true);
      // A remounted form may already hold newer typing when an old acknowledgement arrives.
      if (drafts.get(key) === submitted) {
        drafts.delete(key);
        try { sessionStorage.removeItem(key); } catch { setStorageError(true); }
      }
      void client.invalidateQueries({ queryKey: ['story-map', pid] });
    },
  });
  return <details className="space-y-2 border-t border-border pt-2">
    <summary className="cursor-pointer font-medium">검토안 작성·처리</summary>
    <p className="mt-2 text-muted-foreground">채택은 검토안에 대한 결정입니다. 원고·기억·목표에 반영하려면 해당 편집 화면에서 별도로 저장해 주세요.</p>
    {item.latest_decision && <div className="rounded bg-muted p-2">
      <p>{item.latest_decision.evidence_token === item.evidence_token ? '현재 근거의 최근 결정' : '이전 근거의 결정 · 다시 검토 필요'}</p>
      <DecisionDetail row={item.latest_decision} />
    </div>}
    <div className="grid gap-2 lg:grid-cols-2">
      <div><h5 className="font-semibold">검토 기준 내용</h5><p className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded border p-2">{base.review_text}</p></div>
      <label className="block">작가 검토안
        <textarea aria-label="작가 검토안" rows={7} maxLength={20000} value={proposal} disabled={save.isPending || saved}
          onChange={e => changeDraft({ ...draft, proposal: e.target.value })} className="mt-1 w-full rounded border border-input bg-background p-2" />
      </label>
    </div>
    <label className="block">처리 이유
      <textarea aria-label="처리 이유" rows={2} maxLength={2000} value={reason} disabled={save.isPending || saved}
        onChange={e => changeDraft({ ...draft, reason: e.target.value })} className="mt-1 w-full rounded border border-input bg-background p-2" />
    </label>
    <p className="text-muted-foreground">작성 중인 검토안은 이 탭에서 임시 보관됩니다.</p>
    {storageError && <p role="alert">브라우저 임시 저장에 실패했습니다. 페이지를 새로고침하거나 탭을 닫기 전에 입력 내용을 복사해 주세요.</p>}
    {changed && <p role="status">근거 또는 처리 이력이 변경되었습니다. 입력한 검토안은 유지됩니다. 최신 근거를 확인해 주세요.</p>}
    {save.isError && <p role="alert">{save.error.message} 입력한 내용은 유지됩니다.</p>}
    {saved && <p role="status">검토 결정을 기록했습니다. 원문 변경 경고는 내용을 실제로 갱신할 때까지 유지됩니다.</p>}
    <div className="flex flex-wrap gap-1">
      {(Object.keys(actions) as ReviewDecision['decision'][]).map(action => <Button key={action} size="sm" variant="outline"
        disabled={save.isPending || saved || changed || !reason.trim() || (action === 'adopt' && !proposal.trim())}
        onClick={() => save.mutate({ decision: action, submitted: draft })}>{save.isPending ? '저장 중…' : actions[action]}</Button>)}
      <Button size="sm" variant="ghost" disabled={save.isPending} onClick={async () => {
        await client.invalidateQueries({ queryKey: ['story-map', pid] });
      }}>최신 근거 조회</Button>
      {(changed || saved) && <Button size="sm" variant="outline" disabled={save.isPending} onClick={() => {
        changeDraft({ ...draft, base: item }); setSaved(false); save.reset();
      }}>조회된 근거로 다시 검토</Button>}
    </div>
  </details>;
}

interface History { total: number; offset: number; next_offset: number | null; items: ReviewDecision[] }
export function StoryReviewHistory({ pid }: { pid: number }) {
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ['story-map', pid, 'review-history', offset],
    queryFn: ({ signal }) => api.get<History>(`/projects/${pid}/story-map/review-decisions?offset=${offset}`, { signal }),
    enabled: open,
  });
  return <section className="mt-3 border-t pt-3" aria-label="작품 검토 이력">
    <Button size="sm" variant="outline" aria-expanded={open} onClick={() => setOpen(!open)}>작품 전체 검토 이력 {open ? '접기' : '열기'}</Button>
    {open && <>
      {query.isPending && <p role="status">이력 불러오는 중…</p>}
      {query.isError && <p role="alert">이력을 불러오지 못했습니다. <button className="underline" onClick={() => void query.refetch()}>다시 시도</button></p>}
      {query.data && <>
        <p className="my-2">{query.data.total}건 · 당시 근거에 대한 결정이며 현재 원고 반영 여부를 뜻하지 않습니다.</p>
        <ol className="space-y-2">{query.data.items.map(row => <li className="rounded border border-border p-2" key={row.id}>
          <h5 className="font-semibold">{row.snapshot_json.label} · {row.sequence}번째 기록</h5><DecisionDetail row={row} />
        </li>)}</ol>
        <div className="mt-2 flex gap-2">
          <Button size="sm" variant="outline" disabled={query.data.offset === 0} onClick={() => setOffset(Math.max(0, query.data!.offset - 20))}>이력 이전</Button>
          <Button size="sm" variant="outline" disabled={query.data.next_offset === null} onClick={() => setOffset(query.data!.next_offset ?? 0)}>이력 다음</Button>
        </div>
      </>}
    </>}
  </section>;
}
