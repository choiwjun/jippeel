/**
 * S4 세계관/로어북 (`/projects/{pid}/lore`) — 설계서 §2.4.
 * FR-302 카테고리 필터, FR-304 키워드 검색(GET /search, FTS5), FR-303 키워드 칩,
 * 항목 리스트 + 상세 Sheet(P1 준수 — AI 결과 자동 삽입 없음).
 */
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type LoreCategory, type LoreEntry } from '@/lib/api';
import { useAiPanelStore } from '@/stores/aiPanelStore';
import { toast } from '@/components/ui/toast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Sheet, SheetBody, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Textarea } from '@/components/ui/textarea';

const CATEGORIES: LoreCategory[] = ['용어', '장소', '세력', '기타'];

export function LorebookPage() {
  const params = useParams();
  const pid = Number(params.pid);

  const [category, setCategory] = useState<LoreCategory | '전체'>('전체');
  const [q, setQ] = useState('');
  // FR-304 검색 디바운스 300ms
  const [qDebounced, setQDebounced] = useState('');
  useEffect(() => {
    const t = window.setTimeout(() => setQDebounced(q.trim()), 300);
    return () => window.clearTimeout(t);
  }, [q]);

  const searching = qDebounced.length > 0;
  const listQuery = useQuery({
    queryKey: ['lore', pid, category],
    queryFn: () =>
      api.get<LoreEntry[]>(
        `/projects/${pid}/lore${category !== '전체' ? `?category=${encodeURIComponent(category)}` : ''}`,
      ),
  });
  const searchQuery = useQuery({
    queryKey: ['lore-search', pid, category, qDebounced],
    queryFn: () => {
      const sp = new URLSearchParams({ q: qDebounced });
      if (category !== '전체') sp.set('category', category);
      return api.get<LoreEntry[]>(`/projects/${pid}/lore/search?${sp.toString()}`);
    },
    enabled: searching,
    placeholderData: (prev) => prev,
  });

  const entries = searching ? searchQuery.data : listQuery.data;

  // FR-303 키워드 칩 클릭 → 동일 키워드 필터
  const [keywordFilter, setKeywordFilter] = useState<string | null>(null);
  const filtered = useMemo(() => {
    let rows = entries ?? [];
    if (keywordFilter) rows = rows.filter((e) => (e.keywords ?? []).includes(keywordFilter));
    return rows;
  }, [entries, keywordFilter]);

  const [editingId, setEditingId] = useState<number | 'new' | null>(null);
  const queryClient = useQueryClient();

  return (
    <div className="mx-auto flex h-full max-w-[900px] gap-6 px-6 py-4">
      {/* 카테고리 사이드 필터 (FR-302) */}
      <nav className="hidden w-40 shrink-0 flex-col gap-1 md:flex" aria-label="카테고리 필터">
        <p className="px-2 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">분류</p>
        {(['전체', ...CATEGORIES] as string[]).map((c) => (
          <Button
            key={c}
            size="sm"
            variant={category === c ? 'default' : 'ghost'}
            className="justify-start"
            onClick={() => setCategory(c as LoreCategory | '전체')}
          >
            {c}
          </Button>
        ))}
      </nav>

      <div className="min-w-0 flex-1">
        <header className="mb-3 flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-semibold">로어북 ({filtered.length})</h1>
          <div className="ml-auto flex items-center gap-2">
            <Input
              type="search"
              aria-label="로어북 키워드 검색"
              placeholder="키워드·제목·본문 검색…"
              className="h-8 w-56"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            <Button size="sm" onClick={() => setEditingId('new')}>+ 항목 추가</Button>
          </div>
        </header>

        {keywordFilter && (
          <p className="mb-2 text-sm">
            키워드 <Badge variant="secondary">{keywordFilter}</Badge>
            <Button size="sm" variant="ghost" className="ml-2" onClick={() => setKeywordFilter(null)}>필터 해제</Button>
          </p>
        )}

        {listQuery.isError || (searching && searchQuery.isError) ? (
          <p className="py-8 text-sm text-destructive">목록을 불러올 수 없습니다.</p>
        ) : !entries && !listQuery.isPending ? null : listQuery.isPending ? (
          <p className="py-8 text-sm text-muted-foreground">불러오는 중…</p>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-md border border-dashed border-border py-16">
            <p className="text-sm text-muted-foreground">세계관의 첫 조각을 등록하세요.</p>
          </div>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {filtered.map((entry) => (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => setEditingId(entry.id)}
                  className="w-full rounded-md border border-border bg-card p-3 text-left transition-shadow duration-fast hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="flex items-center gap-2">
                    <Badge variant="outline">{entry.category}</Badge>
                    <span className="font-medium">{entry.title}</span>
                  </span>
                  {(entry.keywords ?? []).length > 0 && (
                    <span className="mt-1.5 flex flex-wrap gap-1">
                      {(entry.keywords ?? []).map((k) => (
                        <span
                          key={k}
                          role="button"
                          tabIndex={0}
                          aria-label={`키워드 ${k}으로 필터`}
                          onClick={(e) => { e.stopPropagation(); setKeywordFilter(k); }}
                          onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); setKeywordFilter(k); } }}
                        >
                          <Badge variant="secondary" className="cursor-pointer">{k}</Badge>
                        </span>
                      ))}
                    </span>
                  )}
                  {entry.content && (
                    <p className="mt-1.5 line-clamp-2 text-sm text-muted-foreground">{entry.content}</p>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {editingId !== null && (
        <LoreDrawer
          pid={pid}
          entryId={editingId}
          onClose={() => {
            setEditingId(null);
            queryClient.invalidateQueries({ queryKey: ['lore', pid] });
            queryClient.invalidateQueries({ queryKey: ['lore-search', pid] });
          }}
        />
      )}
    </div>
  );
}

function LoreDrawer({
  pid,
  entryId,
  onClose,
}: {
  pid: number;
  entryId: number | 'new';
  onClose: () => void;
}) {
  const isNew = entryId === 'new';
  const detailQuery = useQuery({
    queryKey: ['lore-entry', entryId],
    queryFn: () => api.get<LoreEntry>(`/lore/${entryId}`),
    enabled: !isNew,
  });

  const [category, setCategory] = useState<LoreCategory>('기타');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [keywordsText, setKeywordsText] = useState('');
  const [loadedId, setLoadedId] = useState<number | 'new' | null>(isNew ? 'new' : null);
  if (!isNew && detailQuery.data && loadedId !== detailQuery.data.id) {
    setLoadedId(detailQuery.data.id);
    setCategory(detailQuery.data.category);
    setTitle(detailQuery.data.title);
    setContent(detailQuery.data.content ?? '');
    setKeywordsText((detailQuery.data.keywords ?? []).join(', '));
  }

  const save = useMutation({
    /** 본문 저장(PATCH/POST) + keywords[] 전체 교체(PUT, 별도 엔드포인트) 순차 처리 */
    mutationFn: async () => {
      const saved = isNew
        ? await api.post<LoreEntry>(`/projects/${pid}/lore`, {
            category, title: title.trim(), content: content.trim() || null,
          })
        : await api.patch<LoreEntry>(`/lore/${entryId}`, {
            category, title: title.trim(), content: content.trim() || null,
          });
      const kw = keywordsText.split(',').map((s) => s.trim()).filter(Boolean);
      if (!isNew || kw.length > 0) {
        return api.put<LoreEntry>(`/lore/${saved.id}/keywords`, { keywords: kw });
      }
      return saved;
    },
    onSuccess: () => {
      toast('저장되었습니다.', 'success');
      onClose();
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  return (
    <Sheet open onOpenChange={(o) => (!o ? onClose() : undefined)}>
      <SheetHeader>
        <SheetTitle>{isNew ? '새 로어 항목' : detailQuery.data?.title ?? ''}</SheetTitle>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="닫기">닫기</Button>
      </SheetHeader>
      <SheetBody className="flex flex-col gap-3">
        <div>
          <Label htmlFor="lo-cat">분류</Label>
          <Select id="lo-cat" value={category} onChange={(e) => setCategory(e.target.value as LoreCategory)}>
            {CATEGORIES.map((c) => (<option key={c} value={c}>{c}</option>))}
          </Select>
        </div>
        <div>
          <Label htmlFor="lo-title">제목 *</Label>
          <Input id="lo-title" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="lo-content">본문</Label>
          <Textarea id="lo-content" rows={8} value={content} onChange={(e) => setContent(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="lo-keywords">키워드 (콤마 구분 — AI 컨텍스트 자동 주입 기반)</Label>
          <Input id="lo-keywords" value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)} />
        </div>

        <div className="mt-1 flex items-center gap-2">
          <Button
            disabled={save.isPending || !title.trim()}
            onClick={() => save.mutate()}
          >
            저장
          </Button>
          <Button variant="ghost" onClick={onClose}>닫기</Button>
          {!isNew && <AiRefineButton entryId={entryId as number} />}
        </div>
      </SheetBody>
    </Sheet>
  );
}

/** S5 연결 — [AI로 본문 다듬기]. P1: 결과는 S5의 3버튼으로만 반영 */
function AiRefineButton({ entryId }: { entryId: number }) {
  const openAiPanel = useAiPanelStore((s) => s.open);
  const setMode = useAiPanelStore((s) => s.setMode);
  const setContext = useAiPanelStore((s) => s.setContext);
  const setPrompt = useAiPanelStore((s) => s.setPrompt);

  return (
    <Button
      size="sm"
      variant="outline"
      className="ml-auto"
      onClick={() => {
        setMode('ai');
        setContext({ chapterId: null, characterIds: [], loreIds: [entryId] });
        setPrompt('다음 세계관 항목 본문을 간결하고 일관성 있게 다듬어 주세요.');
        openAiPanel();
      }}
    >
      ✨ AI로 본문 다듬기
    </Button>
  );
}
