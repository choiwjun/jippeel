/**
 * canon 모순 검사 Dialog — 고도화 G-023 + 이력(G-041).
 * 현재 회차가 캐릭터·세계관·복선 설정과 모순되는 후보를 LLM으로 검사해 나열.
 * 원고 자동 수정 없음 — 작가 판단 대상. 검사 결과는 이력으로 재조회 가능.
 */
import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { flushManuscriptDraft } from '@/lib/manuscriptDrafts';
import { useAiPanelStore } from '@/stores/aiPanelStore';
import { useEditorStore } from '@/stores/editorStore';
import { AiContextControls } from '@/components/editor/AiContextControls';
import { Button } from '@/components/ui/button';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Badge, type BadgeVariant } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { toast } from '@/components/ui/toast';

interface CanonIssue {
  quote: string;
  reason: string;
  severity: 'info' | 'warn' | 'error';
}

interface CanonCheckResponse {
  run_id: number;
  chapter_id: number;
  model: string | null;
  issues: CanonIssue[];
  checked_context: Record<string, number | string>;
}

interface CanonRun {
  id: number;
  chapter_id: number;
  model: string | null;
  issues_json: CanonIssue[] | null;
  context_json: Record<string, number | string> | null;
  created_at: string;
}

const severityLabel: Record<CanonIssue['severity'], string> = {
  error: '치명', warn: '주의', info: '참고',
};
const severityVariant: Record<CanonIssue['severity'], BadgeVariant> = {
  error: 'done', warn: 'revising', info: 'secondary',
};

type CanonDisplay = {
  token: string;
  origin: {
    projectId: number;
    chapterId: number;
    expectedRevision: number;
    startedAt: number;
  };
  response: CanonCheckResponse;
};

type ActiveCanonRequest = {
  token: string;
  lifetime: number;
  projectId: number;
  chapterId: number;
};

function contextValue(ctx: Record<string, number | string> | undefined, key: string) {
  const value = ctx?.[key];
  return value === undefined || value === null || value === '' ? '-' : String(value);
}

export function CanonDialog({ chapterId }: { chapterId: number | null }) {
  const [open, setOpen] = useState(false);
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [display, setDisplay] = useState<CanonDisplay | null>(null);
  const queryClient = useQueryClient();
  const activeRequest = useRef<ActiveCanonRequest | null>(null);
  const lifetimeRef = useRef(0);
  const projectId = useEditorStore((s) => s.projectId);
  const selectedCharacterCount = useAiPanelStore((s) => s.contextSelection.characterIds.length);

  const cleanupOwnedRequest = (token: string) => {
    if (activeRequest.current?.token === token) {
      useAiPanelStore.getState().clearAiStart(token);
      activeRequest.current = null;
      setPendingToken(null);
    }
  };

  const requestStillActive = (request: ActiveCanonRequest) => {
    const current = activeRequest.current;
    const editor = useEditorStore.getState();
    return current?.token === request.token
      && current.lifetime === request.lifetime
      && current.projectId === request.projectId
      && current.chapterId === request.chapterId
      && lifetimeRef.current === request.lifetime
      && useAiPanelStore.getState().isAiStartCurrent(request.token)
      && editor.projectId === request.projectId
      && editor.chapterId === request.chapterId;
  };

  useEffect(() => () => {
    const active = activeRequest.current;
    if (active) cleanupOwnedRequest(active.token);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const active = activeRequest.current;
    if (active && (active.projectId !== projectId || active.chapterId !== chapterId)) {
      lifetimeRef.current += 1;
      cleanupOwnedRequest(active.token);
    }
    setDisplay((current) =>
      current && current.origin.projectId === projectId && current.origin.chapterId === chapterId
        ? current
        : null,
    );
  }, [projectId, chapterId]); // eslint-disable-line react-hooks/exhaustive-deps

  const runCanon = async () => {
    const store = useAiPanelStore.getState();
    const token = store.reserveAiStart('canon');
    if (token === null) return;
    const before = useEditorStore.getState();
    if (before.projectId === null || before.chapterId === null || before.chapterId !== chapterId) {
      store.clearAiStart(token);
      toast('현재 회차를 확인한 뒤 다시 실행하세요.', 'warning');
      return;
    }

    const request: ActiveCanonRequest = {
      token,
      lifetime: lifetimeRef.current,
      projectId: before.projectId,
      chapterId: before.chapterId,
    };
    activeRequest.current = request;
    setPendingToken(token);
    setDisplay(null);
    const directives = structuredClone(store.getDirectives(before.projectId, before.chapterId));

    let flushed;
    try {
      flushed = await flushManuscriptDraft(before.projectId, before.chapterId);
    } catch (e) {
      if (requestStillActive(request)) {
        cleanupOwnedRequest(token);
        toast(`모순 검사 실패: ${(e as Error).message}`, 'error');
      }
      return;
    }

    if (!requestStillActive(request)) return;
    const origin = {
      projectId: flushed.detail.project_id,
      chapterId: flushed.detail.id,
      expectedRevision: flushed.detail.revision,
      startedAt: Date.now(),
    };

    try {
      const response = await api.post<CanonCheckResponse>('/canon-check', {
        chapter_id: origin.chapterId,
        expected_revision: origin.expectedRevision,
        episode_purpose: directives.episodePurpose,
        approved_foreshadow_ids: directives.approvedForeshadowIds,
        include_relationships: directives.includeRelationships,
      });
      if (!requestStillActive(request) || response.chapter_id !== origin.chapterId) return;
      setDisplay({ token, origin, response });
      queryClient.invalidateQueries({ queryKey: ['canon-runs', origin.chapterId] });
    } catch (e) {
      if (requestStillActive(request)) {
        toast(`모순 검사 실패: ${(e as Error).message}`, 'error');
      }
    } finally {
      cleanupOwnedRequest(token);
    }
  };

  const handleOpenChange = (next: boolean) => {
    if (next) {
      lifetimeRef.current += 1;
      setOpen(true);
      return;
    }
    lifetimeRef.current += 1;
    const active = activeRequest.current;
    if (active) cleanupOwnedRequest(active.token);
    setDisplay(null);
    setOpen(false);
  };

  const historyQuery = useQuery({
    queryKey: ['canon-runs', chapterId],
    queryFn: () => api.get<CanonRun[]>(`/canon-check/runs?chapter_id=${chapterId}`),
    enabled: chapterId !== null && open,
  });

  const currentDisplay = display && display.origin.projectId === projectId && display.origin.chapterId === chapterId
    ? display
    : null;
  const data = currentDisplay?.response;
  const ctx = data?.checked_context;
  const ctxSummary = ctx
    ? `캐릭터 ${ctx.characters ?? 0} · 로어 ${ctx.lore ?? 0} · 복선 ${ctx.foreshadows ?? 0} · 독자 인지 ${ctx.audience_known ?? 0}`
    : '';
  const pending = pendingToken !== null;

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        disabled={chapterId === null}
        onClick={() => handleOpenChange(true)}
        aria-label="canon 모순 검사"
      >
        모순 검사
      </Button>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>연속성(모순) 검사</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <p className="text-[11px] text-muted-foreground">
            현재 회차가 캐릭터 설정·세계관·복선(시간축·위치 포함)과 모순되는 지점을 검사합니다.
            원고는 절대 자동 수정되지 않습니다.
          </p>
          <AiContextControls
            projectId={projectId}
            chapterId={chapterId}
            selectedCharacterCount={selectedCharacterCount}
          />
          <Button
            disabled={chapterId === null || pending}
            onClick={() => void runCanon()}
          >
            {pending ? '검사 중… (수십 초 소요)' : '🔍 검사 실행'}
          </Button>

          {data && (
            <div className="flex flex-col gap-2">
              <p className="text-[11px] text-muted-foreground">
                검사 대상 — {ctxSummary}
              </p>
              <p className="text-[11px] text-muted-foreground">
                검사 기준 — 작품 #{currentDisplay.origin.projectId} · 회차 #{currentDisplay.origin.chapterId} · rev {contextValue(ctx, 'checked_input_revision')} · hash {contextValue(ctx, 'checked_input_hash')}
              </p>
              {data.issues.length === 0 ? (
                <Alert variant="info">
                  <AlertDescription>모순 후보가 없습니다.</AlertDescription>
                </Alert>
              ) : (
                data.issues.map((issue, i) => (
                  <div key={i} className="rounded-md border border-border p-2">
                    <div className="mb-1 flex items-center gap-2">
                      <Badge variant={severityVariant[issue.severity]}>
                        {severityLabel[issue.severity]}
                      </Badge>
                    </div>
                    <p className="text-xs font-medium">“{issue.quote}”</p>
                    <p className="mt-1 text-xs text-muted-foreground">{issue.reason}</p>
                  </div>
                ))
              )}
            </div>
          )}

          <details className="rounded-md border border-border p-2">
            <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">
              검사 이력 ({historyQuery.data?.length ?? 0})
            </summary>
            <div className="mt-2 flex max-h-40 flex-col gap-1.5 overflow-y-auto">
              {(historyQuery.data ?? []).map((r) => (
                <div key={r.id} className="flex items-center justify-between gap-2 text-xs">
                  <span className="text-muted-foreground">
                    {new Date(r.created_at).toLocaleString('ko-KR')}
                  </span>
                  <span>{(r.issues_json ?? []).length}건 · {r.model ?? '-'}</span>
                </div>
              ))}
              {(historyQuery.data ?? []).length === 0 && (
                <p className="text-xs text-muted-foreground">이력 없음</p>
              )}
            </div>
          </details>
        </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
