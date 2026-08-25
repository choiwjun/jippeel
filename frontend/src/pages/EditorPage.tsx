import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type Chapter, type ChapterDetail, type ChapterStatus } from '@/lib/api';
import { useEditorStore } from '@/stores/editorStore';
import { useAiPanelStore } from '@/stores/aiPanelStore';
import { countChars } from '@/lib/wordCount';
import { exportChapter, exportProjectBundle } from '@/lib/export';
import { CodeMirrorEditor } from '@/components/editor/CodeMirrorEditor';
import { EditorPreview } from '@/components/editor/EditorPreview';
import { SaveIndicator } from '@/components/editor/SaveIndicator';
import { WordCountFooter } from '@/components/editor/WordCountFooter';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge, StatusBadge } from '@/components/ui/badge';
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
    if (chapterId === null && chaptersQuery.data && chaptersQuery.data.length > 0) {
      const first = [...chaptersQuery.data].sort(
        (a, b) => a.volume - b.volume || a.sort_order - b.sort_order,
      )[0];
      setContext(pid, first.id);
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
              <PreviewBody chapterId={chapterId} />
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
          aria-label="윤문 리포트 (Sprint 4b)"
        >
          윤문 실행
        </Button>
      </div>
    </div>
  );
}

function PreviewBody({ chapterId }: { chapterId: number }) {
  const detail = useQuery({
    queryKey: ['chapter', chapterId],
    queryFn: () => api.get<ChapterDetail>(`/chapters/${chapterId}`),
  });
  if (detail.isPending) return <p className="p-4 text-sm text-muted-foreground">불러오는 중…</p>;
  if (detail.isError) return <p className="p-4 text-sm text-destructive">{(detail.error as Error).message}</p>;
  return <EditorPreview content={detail.data.content_md} />;
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
        aria-label="회차 상태 변경 (FR-105)"
        className="h-8 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        value={chapter.status}
        onChange={(e) => patchMeta.mutate({ status: e.target.value as ChapterStatus })}
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
            aria-label="메모 편집 (FR-108)"
          >
            메모{chapter.memo ? ' ●' : ''}
          </DropdownMenuTrigger>
          <DropdownMenuContent className="p-2">
            <DropdownMenuLabel>빠른 메모 (FR-108)</DropdownMenuLabel>
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
        <ExportMenu pid={pid} chapter={chapter} />

        <Badge variant="secondary">{chapter.volume}권</Badge>
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
        aria-label="내보내기 메뉴 (FR-109)"
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

function EditorBody({ pid, chapterId }: { pid: number; chapterId: number }) {
  const queryClient = useQueryClient();

  const detail = useQuery({
    queryKey: ['chapter', chapterId],
    queryFn: () => api.get<ChapterDetail>(`/chapters/${chapterId}`),
  });

  const setWordCount = useEditorStore((s) => s.setWordCount);
  const setSaveState = useEditorStore((s) => s.setSaveState);
  const markSaved = useEditorStore((s) => s.markSaved);

  const autoSaveMs = 1500;
  const saveTimerRef = useRef<number | undefined>(undefined);
  const countTimerRef = useRef<number | undefined>(undefined);
  const latestTextRef = useRef<string | null>(null);

  /** FR-106 — PUT /chapters/{cid}/content (자동저장 + Ctrl+S 즉시) */
  const saveNow = useCallback(async () => {
    const text = latestTextRef.current;
    if (text === null || !detail.data || text === detail.data.content_md) return;
    setSaveState('saving');
    try {
      await api.put<ChapterDetail>(`/chapters/${chapterId}/content`, { content_md: text });
      markSaved();
      // 트리의 word_count_cache 갱신 (전체 invalidate로 포커스 뺏김 방지)
      queryClient.setQueryData<Chapter[]>(['chapters', pid], (old) =>
        old?.map((c) =>
          c.id === chapterId ? { ...c, word_count_cache: countChars(text).noSpace } : c,
        ),
      );
    } catch {
      setSaveState('error');
    }
  }, [chapterId, detail.data, markSaved, pid, queryClient, setSaveState]);

  const onChange = useCallback((text: string) => {
    latestTextRef.current = text;

    // FR-104 글자 수 — 200ms 디바운스 실시간 표시
    window.clearTimeout(countTimerRef.current);
    countTimerRef.current = window.setTimeout(() => setWordCount(countChars(text)), 200);

    // FR-106 자동저장 — 디바운스 후 PUT
    const store = useEditorStore.getState();
    if (store.saveState !== 'saving') setSaveState('dirty');
    window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => void saveNow(), autoSaveMs);
  }, [saveNow, setSaveState, setWordCount]);

  // 회차 언로드 시 대기 중인 저장 플러시
  useEffect(() => {
    return () => {
      window.clearTimeout(saveTimerRef.current);
      window.clearTimeout(countTimerRef.current);
      const text = latestTextRef.current;
      if (text !== null && useEditorStore.getState().saveState === 'dirty') {
        // best-effort 동기 저장 — 페이지 이탈 잔여 변경 방지(NFR-204)
        navigator.sendBeacon?.(
          `/api/v1/chapters/${chapterId}/content`,
          new Blob([JSON.stringify({ content_md: text })], { type: 'application/json' }),
        );
      }
    };
  }, [chapterId]);

  if (detail.isPending) return <p className="p-4 text-sm text-muted-foreground">불러오는 중…</p>;
  if (detail.isError) return <p className="p-4 text-sm text-destructive">{(detail.error as Error).message}</p>;

  return (
    <CodeMirrorEditor
      key={chapterId}
      value={detail.data.content_md}
      onChange={onChange}
      onSave={() => void saveNow()}
    />
  );
}
