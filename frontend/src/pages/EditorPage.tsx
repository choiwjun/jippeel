import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type Chapter, type ChapterDetail, type ChapterSnapshotDetail, type ChapterSnapshotMeta, type ChapterStatus } from '@/lib/api';
import { useEditorStore } from '@/stores/editorStore';
import { beginManuscriptReplacement, completeManuscriptReplacement, flushManuscriptDraft, useManuscriptDraft } from '@/lib/manuscriptDrafts';
import { useAiPanelStore } from '@/stores/aiPanelStore';
import { countChars } from '@/lib/wordCount';
import { volumeLabel, volumeSortKey } from '@/lib/api';
import { exportChapter, exportProjectBundle } from '@/lib/export';
import { CodeMirrorEditor } from '@/components/editor/CodeMirrorEditor';
import { EditorPreview } from '@/components/editor/EditorPreview';
import { SaveIndicator } from '@/components/editor/SaveIndicator';
import { WordCountFooter } from '@/components/editor/WordCountFooter';
import { QualityDialog } from '@/components/editor/QualityDialog';
import { CanonDialog } from '@/components/editor/CanonDialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Badge, StatusBadge } from '@/components/ui/badge';
import { toast } from '@/components/ui/toast';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';

const STATUSES: ChapterStatus[] = ['초고', '수정중', '완료'];

/**
 * S2 회차 에디터 (`/projects/{pid}/write`) — M1.
 * FR-103 마크다운 편집(CodeMirror 6) + 미리보기 탭(markdown-it+DOMPurify)
 * FR-104 공백제외 글자 수 실시간(디바운스) · FR-106 자동저장 PUT /chapters/{cid}/content
 * FR-105 상태 칩 · FR-108 빠른 메모(memo) · M-1 내보내기(.txt/.md)
 */
export function EditorPage() {
  const params = useParams();
  const pid = Number(params.pid);

  const chapterId = useEditorStore((s) => s.chapterId);
  const setContext = useEditorStore((s) => s.setContext);
  const mode = useEditorStore((s) => s.mode);
  const setMode = useEditorStore((s) => s.setMode);
  const openAiPanel = useAiPanelStore((s) => s.open);
  const setAiMode = useAiPanelStore((s) => s.setMode);

  // 최초 진입 시 첫 회차 자동 선택
  const chaptersQuery = useQuery({
    queryKey: ['chapters', pid],
    queryFn: () => api.get<Chapter[]>(`/projects/${pid}/chapters`),
    enabled: Number.isFinite(pid),
  });

  useEffect(() => {
    if (useEditorStore.getState().projectId !== pid) setContext(pid, null);
  }, [pid, setContext]);

  useEffect(() => {
    if (!chaptersQuery.data) return;
    const sorted = [...chaptersQuery.data].sort(
      (a, b) => volumeSortKey(a.volume) - volumeSortKey(b.volume) || a.sort_order - b.sort_order,
    );
    const selected = chapterId === null ? null : sorted.find((c) => c.id === chapterId);
    const storeProjectId = useEditorStore.getState().projectId;
    if (!selected) {
      setContext(pid, sorted[0]?.id ?? null);
    } else if (storeProjectId !== pid) {
      setContext(pid, selected.id);
    }
  }, [chapterId, chaptersQuery.data, pid, setContext]);

  return (
    <div className="mx-auto flex h-full max-w-[820px] flex-col px-6">
      <EditorHeader pid={pid} chapterId={chapterId} />
      <div className="min-h-0 flex-1 pb-2">
        {chapterId !== null ? (
          <Tabs
            value={mode}
            onValueChange={(v) => setMode(v as 'edit' | 'preview')}
            className="flex h-full min-h-0 flex-col"
          >
            <TabsList className="mb-2 self-start">
              <TabsTrigger value="edit">편집</TabsTrigger>
              <TabsTrigger value="preview">미리보기</TabsTrigger>
            </TabsList>
            <TabsContent
              value="edit"
              className="thin-scroll min-h-0 min-w-0 flex-1 overflow-y-auto rounded-md border border-border bg-background"
            >
              <EditorBody pid={pid} chapterId={chapterId} />
            </TabsContent>
            <TabsContent
              value="preview"
              className="thin-scroll min-h-0 min-w-0 flex-1 overflow-y-auto rounded-md border border-border bg-card"
            >
              <PreviewBody pid={pid} chapterId={chapterId} />
            </TabsContent>
          </Tabs>
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">
              좌측에서 회차를 선택하거나 ‘+ 회차 추가’로 시작하세요.
            </p>
          </div>
        )}
      </div>
      <WordCountFooter />

      {/* 빠른 액션 (NFR-303) */}
      <div className="fixed bottom-14 right-6 z-30 flex flex-col gap-2">
        <Button size="sm" onClick={() => { setAiMode('ai'); openAiPanel(); }} aria-label="AI 패널 열기 (Alt+A)">
          AI 패널
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => { setAiMode('refine'); openAiPanel(); }}
          aria-label="윤문 리포트"
        >
          윤문 실행
        </Button>
        {/* 고도화 G-031 — 규칙 기반 회차 품질 진단 */}
        <QualityDialog chapterId={chapterId} />
        {/* 고도화 G-023 — canon 모순 검사 */}
        <CanonDialog chapterId={chapterId} />
      </div>
    </div>
  );
}

function PreviewBody({ pid, chapterId }: { pid: number; chapterId: number }) {
  const queryClient = useQueryClient();
  const detail = useQuery({
    queryKey: ['chapter', chapterId],
    queryFn: () => api.get<ChapterDetail>(`/chapters/${chapterId}`),
  });
  const draft = useManuscriptDraft({
    projectId: pid,
    chapterId,
    serverDetail: detail.data,
    onServerDetail: (next) => updateChapterCaches(queryClient, pid, next),
  });
  if (detail.isPending) return <p className="p-4 text-sm text-muted-foreground">불러오는 중…</p>;
  if (detail.isError) return <p className="p-4 text-sm text-destructive">{(detail.error as Error).message}</p>;
  return <EditorPreview content={draft.text} />;
}

function EditorHeader({ pid, chapterId }: { pid: number; chapterId: number | null }) {
  const queryClient = useQueryClient();

  const detail = useQuery({
    queryKey: ['chapter', chapterId],
    queryFn: () => api.get<ChapterDetail>(`/chapters/${chapterId}`),
    enabled: chapterId !== null,
  });

  const patchMeta = useMutation({
    mutationFn: (body: { title?: string; status?: ChapterStatus; memo?: string }) =>
      api.patch<ChapterDetail>(`/chapters/${chapterId}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['chapters', pid] }),
  });

  const chapter = detail.data;
  const [titleDraft, setTitleDraft] = useState('');
  const [memoDraft, setMemoDraft] = useState('');
  const memoTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    setTitleDraft(chapter?.title ?? '');
    setMemoDraft(chapter?.memo ?? '');
  }, [chapter?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (chapterId === null || !chapter) {
    return (
      <div className="flex items-center justify-between py-3">
        <h1 className="text-lg font-semibold">회차 선택</h1>
        <SaveIndicator />
      </div>
    );
  }

  return (
    <header className="flex flex-wrap items-center gap-2 py-3">
      <Input
        className="h-8 w-56 border-transparent bg-transparent text-base font-semibold hover:border-input focus-visible:bg-background"
        value={titleDraft}
        placeholder="회차 제목"
        onChange={(e) => setTitleDraft(e.target.value)}
        onBlur={() => {
          if (titleDraft !== chapter.title) patchMeta.mutate({ title: titleDraft });
        }}
      />
      <StatusBadge status={chapter.status} />
      <select
        aria-label="회차 상태 변경"
        className="h-8 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        value={chapter.status}
        onChange={(e) => {
          const next = e.target.value as ChapterStatus;
          patchMeta.mutate({ status: next });
          // 고도화 G-042 — '완료' 전환 시 후크 자동 점검(차단 없음, 제안만)
          if (next === '완료') {
            void (async () => {
              try {
                const q = await api.get<{ hook_present: boolean; suggested_preset_names: string[] }>(
                  `/chapters/${chapterId}/quality?record=false`);
                if (!q.hook_present) {
                  toast('후크 없이 완료 처리됩니다 — 마지막 문장을 "장 끝 후크" 프리셋으로 다듬으면 다음 화 클릭률이 올라갑니다.', 'warning');
                }
              } catch { /* 점검 실패는 침묵 */ }
            })();
          }
        }}
      >
        {STATUSES.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>

      <SaveIndicator />

      <div className="ml-auto flex items-center gap-1">
        {/* FR-108 빠른 메모 */}
        <DropdownMenu>
          <DropdownMenuTrigger
            className="rounded-md px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted"
            aria-label="메모 편집"
          >
            메모{chapter.memo ? ' ●' : ''}
          </DropdownMenuTrigger>
          <DropdownMenuContent className="p-2">
            <DropdownMenuLabel>빠른 메모</DropdownMenuLabel>
            <textarea
              className="mt-1 min-h-24 w-64 rounded-sm border border-input bg-background p-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={memoDraft}
              onChange={(e) => {
                setMemoDraft(e.target.value);
                window.clearTimeout(memoTimer.current);
                memoTimer.current = window.setTimeout(
                  () => patchMeta.mutate({ memo: e.target.value }),
                  800,
                );
              }}
              placeholder="회차 메모…"
            />
          </DropdownMenuContent>
        </DropdownMenu>

        {/* M-1 / FR-109 내보내기 (.txt/.md) — 현재 회차. 프로젝트 zip 묶음(JSZip)은 Sprint 4b */}
        <SnapshotDialog pid={pid} chapter={chapter} />
        <ExportMenu pid={pid} chapter={chapter} />

        <Badge variant="secondary">{volumeLabel(chapter.volume)}</Badge>
      </div>
    </header>
  );
}

/**
 * FR-109 — 내보내기(.txt/.md). 브라우저 다운로드, 외부 호출 없음.
 * .txt는 마크다운→plain 변환(mdToPlainText), 회차 단건 + 프로젝트 전체 묶음 지원.
 */
function ExportMenu({ pid, chapter }: { pid: number; chapter: ChapterDetail }) {
  // 프로젝트 묶음 — 전 회차 본문 로드 후 연결 파일 생성(zip 미사용 단일 묶음)
  const chaptersQuery = useQuery({
    queryKey: ['chapters', pid],
    queryFn: () => api.get<Chapter[]>(`/projects/${pid}/chapters`),
    enabled: false,
  });

  const exportProject = async (ext: 'txt' | 'md') => {
    try {
      let metas = chaptersQuery.data;
      if (!metas) {
        metas = await api.get<Chapter[]>(`/projects/${pid}/chapters`);
      }
      const details = await Promise.all(
        metas.map((c) => api.get<ChapterDetail>(`/chapters/${c.id}`)),
      );
      exportProjectBundle(`project-${pid}`, details, ext);
    } catch (e) {
      alert(`내보내기 실패: ${(e as Error).message}`);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="rounded-md px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted"
        aria-label="내보내기 메뉴"
      >
        내보내기 ▾
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>회차 내보내기</DropdownMenuLabel>
        <DropdownMenuItem onClick={() => exportChapter(chapter, 'md')}>마크다운 (.md)</DropdownMenuItem>
        <DropdownMenuItem onClick={() => exportChapter(chapter, 'txt')}>텍스트 (.txt)</DropdownMenuItem>
        <DropdownMenuLabel>프로젝트 묶음 내보내기</DropdownMenuLabel>
        <DropdownMenuItem onClick={() => void exportProject('md')}>전 회차 마크다운 (.md)</DropdownMenuItem>
        <DropdownMenuItem onClick={() => void exportProject('txt')}>전 회차 텍스트 (.txt)</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function updateChapterCaches(queryClient: ReturnType<typeof useQueryClient>, pid: number, detail: ChapterDetail) {
  queryClient.setQueryData<ChapterDetail>(['chapter', detail.id], detail);
  queryClient.setQueryData<Chapter[]>(['chapters', pid], (old) =>
    old?.map((c) =>
      c.id === detail.id
        ? {
            ...c,
            title: detail.title,
            status: detail.status,
            memo: detail.memo,
            volume: detail.volume,
            sort_order: detail.sort_order,
            word_count_cache: countChars(detail.content_md).novelpia,
            revision: detail.revision,
            updated_at: detail.updated_at,
          }
        : c,
    ),
  );
}

function SnapshotDialog({ pid, chapter }: { pid: number; chapter: ChapterDetail }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const snapshots = useQuery({
    queryKey: ['chapter-snapshots', chapter.id],
    queryFn: () => api.get<ChapterSnapshotMeta[]>(`/chapters/${chapter.id}/snapshots`),
    enabled: open,
  });
  const selected = useQuery({
    queryKey: ['chapter-snapshot', chapter.id, selectedId],
    queryFn: () => api.get<ChapterSnapshotDetail>(`/chapters/${chapter.id}/snapshots/${selectedId}`),
    enabled: open && selectedId !== null,
  });

  const restore = useMutation({
    mutationFn: async (snapshotId: number) => {
      const flushed = await flushManuscriptDraft(pid, chapter.id);
      const token = beginManuscriptReplacement(pid, chapter.id);
      const detail = await api.post<ChapterDetail>(`/chapters/${chapter.id}/restore`, {
        snapshot_id: snapshotId,
        expected_revision: flushed.detail.revision,
      });
      return { detail, token };
    },
    onSuccess: ({ detail, token }) => {
      const result = completeManuscriptReplacement(pid, chapter.id, detail, token);
      updateChapterCaches(queryClient, pid, detail);
      queryClient.invalidateQueries({ queryKey: ['chapter-snapshots', chapter.id] });
      if (result === 'late_edit') {
        toast('복구 결과는 서버에 반영됐지만 새 입력이 있어 로컬 원고를 보존했습니다.', 'warning');
      } else {
        toast('복구본을 현재 원고로 복원했습니다.', 'success');
        setOpen(false);
        setSelectedId(null);
      }
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  return (
    <>
      <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setOpen(true)}>
        복구본
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>회차 복구본</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 md:grid-cols-[220px_1fr]">
            <div className="thin-scroll max-h-72 overflow-y-auto rounded-md border border-border">
              {snapshots.isPending && <p className="p-3 text-sm text-muted-foreground">복구본 불러오는 중…</p>}
              {snapshots.isError && <p className="p-3 text-sm text-destructive">복구본을 불러올 수 없습니다.</p>}
              {snapshots.data?.length === 0 && <p className="p-3 text-sm text-muted-foreground">아직 복구본이 없습니다.</p>}
              {snapshots.data?.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className="block w-full border-b border-border px-3 py-2 text-left text-xs hover:bg-muted last:border-b-0"
                  onClick={() => setSelectedId(s.id)}
                >
                  revision {s.revision} · {s.reason}
                  <br />
                  <span className="text-muted-foreground">{new Date(s.created_at).toLocaleString('ko-KR')}</span>
                </button>
              ))}
            </div>
            <div className="min-h-48 rounded-md border border-border bg-background p-3">
              {selected.isPending && selectedId !== null && <p className="text-sm text-muted-foreground">원문 불러오는 중…</p>}
              {!selectedId && <p className="text-sm text-muted-foreground">왼쪽에서 복구본을 고르면 원문을 먼저 확인합니다.</p>}
              {selected.data && (
                <div className="flex h-full flex-col gap-2">
                  <p className="text-xs text-muted-foreground">복구본 revision {selected.data.revision} 원문</p>
                  <pre className="thin-scroll max-h-56 flex-1 overflow-y-auto whitespace-pre-wrap rounded-sm bg-muted p-2 font-serif text-sm">
                    {selected.data.content_md}
                  </pre>
                  <Button
                    size="sm"
                    disabled={restore.isPending}
                    onClick={() => restore.mutate(selected.data.id)}
                  >
                    이 복구본으로 복원
                  </Button>
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>닫기</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function DraftPanels({
  draft,
}: {
  draft: ReturnType<typeof useManuscriptDraft>;
}) {
  const copy = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast(`${label}을 클립보드에 복사했습니다.`, 'success');
    } catch {
      toast('클립보드 접근이 거부되었습니다.', 'error');
    }
  };

  return (
    <div className="space-y-2 border-b border-border p-3">
      {draft.storageError && (
        <Alert variant="warning">
          <AlertDescription>{draft.storageError}</AlertDescription>
        </Alert>
      )}
      {draft.errorMessage && draft.saveState === 'error' && (
        <Alert variant="error">
          <AlertDescription>
            {draft.errorMessage} 로컬 원고는 화면과 브라우저 복구본에 보존됩니다.
          </AlertDescription>
        </Alert>
      )}
      {draft.recovery && (
        <Alert variant={draft.recovery.kind === 'mismatch' ? 'warning' : 'info'}>
          <AlertDescription>
            <div className="flex flex-col gap-2">
              <p>{draft.recovery.message}</p>
              {draft.recovery.kind === 'mismatch' && (
                <div className="grid gap-2 md:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold">로컬 복구본 (base revision {draft.recovery.baseRevision})</p>
                    <pre className="max-h-36 overflow-auto whitespace-pre-wrap rounded-sm bg-background p-2 font-serif text-xs">{draft.recovery.localText}</pre>
                  </div>
                  <div>
                    <p className="text-xs font-semibold">서버 원고 (revision {draft.recovery.serverRevision})</p>
                    <pre className="max-h-36 overflow-auto whitespace-pre-wrap rounded-sm bg-background p-2 font-serif text-xs">{draft.recovery.serverText}</pre>
                  </div>
                  <div className="col-span-full flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => draft.useRecoveryText(draft.recovery!.localText)}>
                      로컬 복구본 불러오기
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => void copy(draft.recovery!.localText, '로컬 복구본')}>
                      로컬 복구본 복사
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => void draft.refreshRecoveryServerText()}>
                      서버 원고 새로고침
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => void draft.clearRecovery()}>
                      서버 원고로 계속
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </AlertDescription>
        </Alert>
      )}
      {draft.conflict && (
        <Alert variant="error">
          <AlertDescription>
            <div className="flex flex-col gap-2">
              <p>
                저장 충돌: {draft.conflict.message}
                {draft.conflict.currentRevision != null ? ` (current_revision ${draft.conflict.currentRevision})` : ''}
              </p>
              <div className="grid gap-2 md:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold">로컬 원고</p>
                  <pre className="max-h-36 overflow-auto whitespace-pre-wrap rounded-sm bg-background p-2 font-serif text-xs">{draft.conflict.localText}</pre>
                </div>
                <div>
                  <p className="text-xs font-semibold">서버 원고{draft.conflict.serverRevision != null ? ` revision ${draft.conflict.serverRevision}` : ''}</p>
                  <pre className="max-h-36 overflow-auto whitespace-pre-wrap rounded-sm bg-background p-2 font-serif text-xs">{draft.conflict.serverText ?? '서버 원고를 다시 불러오지 못했습니다.'}</pre>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => void copy(draft.conflict!.localText, '로컬 원고')}>로컬 원고 복사</Button>
                {draft.conflict.serverText && (
                  <Button size="sm" variant="ghost" onClick={() => void copy(draft.conflict!.serverText!, '서버 원고')}>서버 원고 복사</Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => draft.clearConflictKeepingLocal()}>로컬 원고로 다시 저장 시도</Button>
              </div>
            </div>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

function EditorBody({ pid, chapterId }: { pid: number; chapterId: number }) {
  const queryClient = useQueryClient();

  const detail = useQuery({
    queryKey: ['chapter', chapterId],
    queryFn: () => api.get<ChapterDetail>(`/chapters/${chapterId}`),
  });

  const setWordCount = useEditorStore((s) => s.setWordCount);
  const setSaveState = useEditorStore((s) => s.setSaveState);
  const markSaved = useEditorStore((s) => s.markSaved);

  const draft = useManuscriptDraft({
    projectId: pid,
    chapterId,
    serverDetail: detail.data,
    onServerDetail: (next) => updateChapterCaches(queryClient, pid, next),
  });

  const countTimerRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (draft.saveState === 'saved') markSaved();
    else setSaveState(draft.saveState);
  }, [draft.saveState, markSaved, setSaveState]);

  useEffect(() => {
    window.clearTimeout(countTimerRef.current);
    countTimerRef.current = window.setTimeout(() => setWordCount(countChars(draft.text)), 200);
    return () => window.clearTimeout(countTimerRef.current);
  }, [draft.text, setWordCount]);

  const onChange = useCallback((text: string) => {
    draft.edit(text);
  }, [draft]);

  if (detail.isPending) return <p className="p-4 text-sm text-muted-foreground">불러오는 중…</p>;
  if (detail.isError) return <p className="p-4 text-sm text-destructive">{(detail.error as Error).message}</p>;
  if (detail.data.project_id !== pid) {
    return <p className="p-4 text-sm text-destructive">이 회차는 현재 작품에 속하지 않습니다.</p>;
  }

  return (
    <div className="min-h-full">
      <DraftPanels draft={draft} />
      {draft.recovery?.kind === 'mismatch' ? (
        <div className="m-3 rounded-md border border-dashed border-warning/60 bg-warning/10 p-4 text-sm text-warning-foreground">
          복구 선택 전에는 편집이 잠겨 있습니다. 로컬 복구본을 불러오거나 서버 원고로 계속할지 먼저 선택하세요.
        </div>
      ) : (
        <CodeMirrorEditor
          key={`${pid}:${chapterId}`}
          value={draft.text}
          onChange={onChange}
          onSave={() => void draft.flush().catch((e) => toast((e as Error).message, 'error'))}
        />
      )}
    </div>
  );
}
