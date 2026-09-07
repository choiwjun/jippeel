/**
 * S5 AI 패널 (설계서 §2.5) — RightPanel Sheet 본체.
 *
 * P1 (FR-406): 결과는 절대 자동 삽입하지 않는다. [끼워넣기][선택 교체][복사] 3버튼만.
 * NFR-201: 상단 전송 고지 Alert 고정 — 컨텍스트 전송 사실을 매 호출 인지.
 * FR-405: fetch 스트림(SSE) 소비 — EventSource 미사용(lib/aiStream.ts).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ShieldCheckIcon, CloudUploadIcon } from '@/components/ui/icons';
import { useQuery } from '@tanstack/react-query';
import { api, type AiEndpoint, type ChapterDetail, type PromptPreset, volumeLabel } from '@/lib/api';
import { streamGenerate, streamParallelGenerate } from '@/lib/aiStream';
import { useAiPanelStore } from '@/stores/aiPanelStore';
import { useEditorStore } from '@/stores/editorStore';
import { toast } from '@/components/ui/toast';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Textarea } from '@/components/ui/textarea';

/**
 * 회차 브리프 직렬화 — 성공 시 전송 객체, 실패 시 사유를 반환한다.
 * 'incomplete'는 필수 항목 미입력(기존 동작 유지: brief 없이 생성),
 * 'invalid'는 검증 위반(백엔드 계약 위반이므로 조용히 버리지 않고 경고 후 미전송).
 */
type ParsedBrief =
  | { ok: true; brief: Record<string, unknown> }
  | { ok: false; reason: 'incomplete' }
  | { ok: false; reason: 'invalid'; message: string };

function parseEpisodeBrief(brief: EpisodeBriefState): ParsedBrief {
  const lines = (raw: string) =>
    raw.split('\n').map((s) => s.trim()).filter((s) => s.length > 0);
  const emotionGoal = brief.emotion_goal.trim();
  const coreEvents = lines(brief.core_events);
  const characterChoices = lines(brief.character_choices);
  const cost = brief.cost.trim();
  const prohibitions = lines(brief.prohibitions);
  const nextHook = brief.next_hook.trim();
  if (
    !emotionGoal || coreEvents.length === 0 || characterChoices.length === 0
    || !cost || prohibitions.length === 0 || !nextHook
  ) {
    return { ok: false, reason: 'incomplete' };
  }
  // 백엔드 EpisodeBrief 계약 — 위반 시 422가 되므로 전송하지 않는다
  if (coreEvents.length > 3) {
    return { ok: false, reason: 'invalid', message: '핵심 사건은 최대 3개까지 입력할 수 있습니다.' };
  }
  if (characterChoices.length > 4) {
    return { ok: false, reason: 'invalid', message: '인물 선택은 최대 4개까지 입력할 수 있습니다.' };
  }
  if (prohibitions.length > 10) {
    return { ok: false, reason: 'invalid', message: '금지사항은 최대 10개까지 입력할 수 있습니다.' };
  }
  if (emotionGoal.length > 500) {
    return { ok: false, reason: 'invalid', message: '감정 목표는 500자 이내로 입력하세요.' };
  }
  if (cost.length > 500) {
    return { ok: false, reason: 'invalid', message: '대가는 500자 이내로 입력하세요.' };
  }
  if (nextHook.length > 500) {
    return { ok: false, reason: 'invalid', message: '다음 화 훅은 500자 이내로 입력하세요.' };
  }
  if ([...coreEvents, ...characterChoices, ...prohibitions].some((s) => s.length > 500)) {
    return { ok: false, reason: 'invalid', message: '브리프 항목 하나는 500자 이내로 입력하세요.' };
  }
  const target = Number(brief.target_chars_novelpia);
  if (
    brief.target_chars_novelpia !== ''
    && (!Number.isInteger(target) || target < 1000 || target > 10000)
  ) {
    return { ok: false, reason: 'invalid', message: '목표 글자 수는 1000~10000 사이의 정수로 입력하세요.' };
  }
  const out: Record<string, unknown> = {
    emotion_goal: emotionGoal,
    core_events: coreEvents,
    character_choices: characterChoices,
    cost,
    prohibitions,
    next_hook: nextHook,
  };
  if (brief.scene_type) out.scene_type = brief.scene_type;
  if (brief.target_chars_novelpia !== '') out.target_chars_novelpia = target;
  return { ok: true, brief: out };
}

export function AiPanel() {
  // 폼 상태
  const endpointId = useAiPanelStore((s) => s.endpointId);
  const setEndpoint = useAiPanelStore((s) => s.setEndpoint);
  const presetId = useAiPanelStore((s) => s.presetId);
  const setPreset = useAiPanelStore((s) => s.setPreset);
  const model = useAiPanelStore((s) => s.model);
  const setModel = useAiPanelStore((s) => s.setModel);
  const promptOverride = useAiPanelStore((s) => s.promptOverride);
  const setPrompt = useAiPanelStore((s) => s.setPrompt);
  const temperature = useAiPanelStore((s) => s.temperature);
  const maxTokens = useAiPanelStore((s) => s.maxTokens);
  const setParams = useAiPanelStore((s) => s.setParams);
  const reviewPass = useAiPanelStore((s) => s.reviewPass);
  const setReviewPass = useAiPanelStore((s) => s.setReviewPass);
  const reviewEffort = useAiPanelStore((s) => s.reviewEffort);
  const setReviewEffort = useAiPanelStore((s) => s.setReviewEffort);
  const generationMode = useAiPanelStore((s) => s.generationMode);
  const setGenerationMode = useAiPanelStore((s) => s.setGenerationMode);
  const workerLimit = useAiPanelStore((s) => s.workerLimit);
  const setWorkerLimit = useAiPanelStore((s) => s.setWorkerLimit);
  const reviewEndpointId = useAiPanelStore((s) => s.reviewEndpointId);
  const setReviewEndpointId = useAiPanelStore((s) => s.setReviewEndpointId);
  const parallelReviewModel = useAiPanelStore((s) => s.parallelReviewModel);
  const setParallelReviewModel = useAiPanelStore((s) => s.setParallelReviewModel);
  const parallelReviewEffort = useAiPanelStore((s) => s.parallelReviewEffort);
  const setParallelReviewEffort = useAiPanelStore((s) => s.setParallelReviewEffort);
  const parallelProgress = useAiPanelStore((s) => s.parallelProgress);

  // 컨텍스트 + 스트리밍
  const ctx = useAiPanelStore((s) => s.contextSelection);
  const setContext = useAiPanelStore((s) => s.setContext);
  const pendingGenerate = useAiPanelStore((s) => s.pendingGenerate);
  const status = useAiPanelStore((s) => s.status);
  const streamingText = useAiPanelStore((s) => s.streamingText);
  const error = useAiPanelStore((s) => s.error);

  // 서버 데이터
  const endpointsQuery = useQuery({
    queryKey: ['ai-endpoints'],
    queryFn: () => api.get<AiEndpoint[]>('/ai/endpoints'),
  });
  const presetsQuery = useQuery({
    queryKey: ['ai-presets'],
    queryFn: () => api.get<PromptPreset[]>('/ai/presets'),
  });

  const endpoints = useMemo(() => endpointsQuery.data ?? [], [endpointsQuery.data]);
  const selectedPreset = useMemo(
    () => (presetsQuery.data ?? []).find((p) => p.id === presetId) ?? null,
    [presetsQuery.data, presetId],
  );
  const activeEndpoint = endpoints.find((e) => e.id === endpointId)
    ?? endpoints.find((e) => e.is_default)
    ?? endpoints[0];
  const reviewEndpoint = endpoints.find((e) => e.id === reviewEndpointId) ?? activeEndpoint;

  // 엔드포인트 자동 선택(기본 엔드포인트 우선) — 로딩 완료 시 선택이 없으면 첫 엔드포인트 확정
  useEffect(() => {
    if (activeEndpoint && endpointId !== activeEndpoint.id) {
      setEndpoint(activeEndpoint.id);
    }
  }, [activeEndpoint, endpointId, setEndpoint]);

  // 모델 목록 (FR-401 — 백엔드 프록시 GET /models, 5분 캐시)
  const modelsQuery = useQuery({
    queryKey: ['endpoint-models', endpointId],
    queryFn: () => api.get<{ data: Array<{ id: string }> }>(`/ai/endpoints/${endpointId}/models`),
    enabled: endpointId !== null,
    staleTime: 5 * 60_000,
    retry: false,
  });
  const models = modelsQuery.data?.data?.map((m) => m.id) ?? [];
  const reviewModelsQuery = useQuery({
    queryKey: ['endpoint-models', reviewEndpoint?.id],
    queryFn: () => api.get<{ data: Array<{ id: string }> }>(`/ai/endpoints/${reviewEndpoint?.id}/models`),
    enabled: generationMode === 'parallel' && reviewEndpoint?.id != null,
    staleTime: 5 * 60_000,
    retry: false,
  });
  const reviewModels = reviewModelsQuery.data?.data?.map((m) => m.id) ?? [];

  /**
   * 스트림 제어 — abort 소유권은 aiPanelStore(모듈 스코프)로 이전.
   * 언마운트 클린업 없음: 쿼리 settle 등으로 인한 재마운트가 스트림을 죽이지 않는다.
   * 패널 의도적 닫힘(close/toggle-off) 시에만 store.close()가 abort한다.
   */
  const generate = useCallback(() => {
    const store = useAiPanelStore.getState();
    if (!activeEndpoint) {
      if (endpointsQuery.isLoading || presetsQuery.isLoading) {
        // 조기 반환 금지 — 안내 후 settle 시 1회 자동 재시도(아래 effect)
        if (!store.pendingGenerate) {
          store.setPendingGenerate(true);
          toast('엔드포인트를 불러오는 중입니다. 완료되면 자동으로 시작합니다.', 'info');
        }
        return;
      }
      toast('AI 엔드포인트를 먼저 등록하세요 (S7 설정).', 'warning');
      return;
    }
    if (!store.presetId && !store.promptOverride.trim()) {
      toast('프리셋을 고르거나 프롬프트를 입력하세요.', 'warning');
      return;
    }
    const c = store.contextSelection;
    // 회차 브리프 — 필수 항목이 모두 채워졌을 때만 context.brief로 전송.
    // 검증 위반(개수·500자·목표 글자 수 범위)은 조용히 버리지 않고 경고 후 미전송한다.
    const parsedBrief = parseEpisodeBrief(store.episodeBrief);
    if (!parsedBrief.ok && parsedBrief.reason === 'invalid') {
      toast(`브리프를 전송하지 않습니다 — ${parsedBrief.message}`, 'warning');
    }
    const brief = parsedBrief.ok ? parsedBrief.brief : null;
    const parallel = store.generationMode === 'parallel';
    const body = {
      endpoint_id: activeEndpoint.id,
      preset_id: store.presetId,
      prompt_override: store.promptOverride.trim() || null,
      context: {
        chapter_id: c.includeChapter ? c.chapterId : null,
        character_ids: c.includeCharacters ? c.characterIds : [],
        lore_ids: c.includeLore ? c.loreIds : [],
        auto_lore: c.autoLore,
        auto_lore_semantic: c.autoLoreSemantic,
        auto_outline: c.autoOutline,
        auto_foreshadow: c.autoForeshadow,
        scene_id: c.sceneId,
        style_profile: c.styleProfile,
        ...(brief ? { brief } : {}),
      },
      params: {
        model: store.model || undefined,
        temperature: activeEndpoint?.temperature == null ? undefined : store.temperature,
        max_tokens: store.maxTokens,
      },
      ...(parallel
        ? {
            worker_limit: store.workerLimit,
            generation_reasoning_effort: 'medium',
            review: {
              endpoint_id: reviewEndpoint?.id ?? activeEndpoint.id,
              model: store.parallelReviewModel || undefined,
              reasoning_effort: store.parallelReviewEffort || 'xhigh',
            },
          }
        : {
            review: store.reviewPass
              ? { reasoning_effort: store.reviewEffort || undefined }
              : null,
          }),
    };
    store.startStream();
    const stream = parallel ? streamParallelGenerate : streamGenerate;
    useAiPanelStore.getState().setAbort(stream(body, {
      onChunk: (d) => useAiPanelStore.getState().appendChunk(d),
      onStart: (info) => {
        const st = useAiPanelStore.getState();
        st.setInjectedLore(info.injectedLore);
        st.setInjectedForeshadows(info.injectedForeshadows);
        st.setInjectedOutline(info.injectedOutline);
      },
      onParallelStart: (info) => {
        const st = useAiPanelStore.getState();
        st.setInjectedLore(info.injectedLore);
        st.setInjectedForeshadows(info.injectedForeshadows);
        st.setInjectedOutline(info.injectedOutline);
        st.setParallelProgress({ phase: 'planning', sceneCount: 0, started: 0, completed: 0, workerLimit: info.workerLimit });
      },
      onPlannerDone: (info) => useAiPanelStore.getState().setParallelProgress({
        phase: 'workers', sceneCount: info.sceneCount, started: 0, completed: 0,
      }),
      onWorkerStart: () => {
        const st = useAiPanelStore.getState();
        st.setParallelProgress({ started: st.parallelProgress.started + 1 });
      },
      onWorkerDone: () => {
        const st = useAiPanelStore.getState();
        st.setParallelProgress({ completed: st.parallelProgress.completed + 1 });
      },
      onReviewStart: (info) => {
        const st = useAiPanelStore.getState();
        st.setReviewInfo({ model: info.model, endpoint: info.endpoint });
        st.setParallelProgress({ phase: 'review' });
        if (st.resultTab !== 'review') st.setResultTab('review');
      },
      onReviewChunk: (d) => useAiPanelStore.getState().appendReviewChunk(d),
      onRefinedChunk: (d) => {
        const st = useAiPanelStore.getState();
        if (st.resultTab !== 'refined') st.setResultTab('refined');
        st.appendRefinedChunk(d);
      },
      onReviewError: (msg) => toast(msg, 'warning'),
      onParallelError: (msg, stage) => {
        if (stage === 'generation') useAiPanelStore.getState().failStream(msg);
        toast(msg, stage === 'review' ? 'warning' : 'error');
      },
      onDone: () => {
        if (useAiPanelStore.getState().status === 'streaming') {
          useAiPanelStore.getState().finishStream();
        }
      },
      onError: (msg) => {
        useAiPanelStore.getState().failStream(msg);
        toast(msg, 'error');
      },
    }));
  }, [activeEndpoint, reviewEndpoint, endpointsQuery.isLoading, presetsQuery.isLoading]);

  // endpoints/presets 로딩 중 클릭된 생성 요청 — settle 후 1회 자동 재시도
  useEffect(() => {
    if (!pendingGenerate || endpointsQuery.isLoading || !activeEndpoint) return;
    useAiPanelStore.getState().setPendingGenerate(false);
    generate();
  }, [generate, pendingGenerate, activeEndpoint, endpointsQuery.isLoading]);

  const stop = useCallback(() => {
    const st = useAiPanelStore.getState();
    st.abortStream();
    if (useAiPanelStore.getState().status === 'streaming') {
      useAiPanelStore.getState().finishStream();
    }
  }, []);

  const hasResult = status === 'done' && streamingText.length > 0;

  return (
    <div className="flex flex-col gap-3">
      {/* P1 가드 (FR-406) */}
      <Alert variant="info">
        <ShieldCheckSlot />
        <AlertDescription>
          AI 결과는 자동으로 본문에 들어가지 않습니다. ‘끼워넣기’ 또는 ‘선택 교체’를 눌러야 반영됩니다.
        </AlertDescription>
      </Alert>
      {/* NFR-201 전송 고지 (M-2) — 브리프 포함 */}
      <Alert variant="warning">
        <CloudUploadSlot />
        <AlertDescription>
          선택한 회차·카드·로어북·이번 화 브리프 내용은 지정한 LLM 엔드포인트로 전송됩니다.
        </AlertDescription>
      </Alert>

      {/* 호출 컨텍스트 (FR-401/407) */}
      <section className="rounded-md border border-border p-3">
        <h3 className="mb-2 text-xs font-semibold text-muted-foreground">호출 컨텍스트</h3>
        <div className="grid grid-cols-2 gap-2">
          <div className="col-span-2">
            <Label htmlFor="ai-endpoint">엔드포인트</Label>
            <Select
              id="ai-endpoint"
              value={endpointId ?? ''}
              onChange={(e) => setEndpoint(Number(e.target.value))}
              disabled={endpoints.length === 0}
            >
              {endpointsQuery.isLoading && <option value="">엔드포인트 불러오는 중…</option>}
              {!endpointsQuery.isLoading && endpoints.length === 0 && (
                <option value="">등록된 엔드포인트 없음</option>
              )}
              {endpoints.map((ep) => (
                <option key={ep.id} value={ep.id}>
                  {ep.name}{ep.is_default ? ' (기본)' : ''}
                </option>
              ))}
            </Select>
          </div>
          <div className="col-span-2">
            <Label htmlFor="ai-model">모델 {modelsQuery.isError ? '(목록 조회 실패 — 기본 모델 사용)' : ''}</Label>
            <Select id="ai-model" value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="">엔드포인트 기본 모델</option>
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </Select>
          </div>
          <div>
            {activeEndpoint?.temperature == null ? (
              <>
                <Label htmlFor="ai-temp">temperature 미지원</Label>
                <p className="text-[11px] leading-snug text-muted-foreground">
                  이 엔드포인트는 온도를 설정하지 않습니다(설정에서 미설정 상태).
                </p>
              </>
            ) : (
              <>
                <Label htmlFor="ai-temp">temperature {temperature.toFixed(1)}</Label>
                <Slider
                  id="ai-temp"
                  min={0}
                  max={2}
                  step={0.1}
                  value={temperature}
                  onChange={(e) => setParams({ temperature: Number(e.target.value) })}
                />
              </>
            )}
          </div>
          <div>
            <Label htmlFor="ai-maxtok">max_tokens {maxTokens.toLocaleString()}</Label>
            <Slider
              id="ai-maxtok"
              min={256}
              max={8192}
              step={256}
              value={maxTokens}
              onChange={(e) => setParams({ maxTokens: Number(e.target.value) })}
            />
          </div>
        </div>
      </section>

      {/* 프롬프트 (FR-403) */}
      <section className="rounded-md border border-border p-3">
        <h3 className="mb-2 text-xs font-semibold text-muted-foreground">프롬프트</h3>
        <Label htmlFor="ai-preset">프리셋</Label>
        <Select
          id="ai-preset"
          className="mb-2"
          value={presetId ?? ''}
          onChange={(e) => setPreset(e.target.value === '' ? null : Number(e.target.value))}
        >
          <option value="">직접 입력</option>
          {(presetsQuery.data ?? []).map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </Select>
        {selectedPreset && (
          <p className="mb-2 rounded-sm bg-muted px-2 py-1.5 text-[11px] leading-snug text-muted-foreground">
            <span className="font-medium text-foreground">{selectedPreset.name}: </span>
            {selectedPreset.template_text}
          </p>
        )}
        <Textarea
          aria-label="프롬프트 직접 입력"
          placeholder="무엇을 쓸지 지시하세요…"
          rows={4}
          value={promptOverride}
          onChange={(e) => setPrompt(e.target.value)}
        />
      </section>

      {/* 생성 엔진 — 기존 단일 흐름과 선택적 병렬 흐름 */}
      <section className="rounded-md border border-border p-3">
        <h3 className="mb-2 text-xs font-semibold text-muted-foreground">생성 엔진</h3>
        <Label htmlFor="ai-generation-mode">집필 모드</Label>
        <Select
          id="ai-generation-mode"
          value={generationMode}
          onChange={(e) => setGenerationMode(e.target.value as 'single' | 'parallel')}
        >
          <option value="single">단일 생성 (기존 흐름)</option>
          <option value="parallel">병렬 장면 집필 + 전체 감수</option>
        </Select>
        {generationMode === 'parallel' && (
          <div className="mt-2 space-y-2">
            <div>
              <Label htmlFor="ai-worker-limit">동시 장면 수: {workerLimit}</Label>
              <Slider
                id="ai-worker-limit"
                min={2}
                max={4}
                step={1}
                value={workerLimit}
                onChange={(e) => setWorkerLimit(Number(e.target.value))}
              />
            </div>
            <div>
              <Label htmlFor="ai-review-endpoint">전체 감수 엔드포인트</Label>
              <Select
                id="ai-review-endpoint"
                value={reviewEndpointId ?? activeEndpoint?.id ?? ''}
                onChange={(e) => {
                  setReviewEndpointId(e.target.value === '' ? null : Number(e.target.value));
                  setParallelReviewModel('');
                }}
              >
                {endpoints.map((ep) => (
                  <option key={ep.id} value={ep.id}>
                    {ep.name}{ep.is_default ? ' (기본)' : ''}
                  </option>
                ))}
              </Select>
              <Label className="mt-2 block" htmlFor="ai-review-model">감수 모델</Label>
              <Select
                id="ai-review-model"
                value={parallelReviewModel}
                onChange={(e) => setParallelReviewModel(e.target.value)}
              >
                <option value="">엔드포인트 기본 모델</option>
                {reviewModels.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </Select>
              <Label className="mt-2 block" htmlFor="ai-parallel-review-effort">감수 추론 강도</Label>
              <Select
                id="ai-parallel-review-effort"
                value={parallelReviewEffort}
                onChange={(e) => setParallelReviewEffort(e.target.value as AiPanelState['parallelReviewEffort'])}
              >
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
                <option value="xhigh">xhigh (권장)</option>
              </Select>
              <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
                Planner와 장면 worker는 현재 엔드포인트를 사용하고, 조립 후 선택한 감수 모델로 전체 원고를 감수합니다.
              </p>
            </div>
          </div>
        )}
      </section>

      {/* 이번 화 브리프 — 필수 항목이 모두 채워졌을 때만 context.brief로 전송 */}
      <EpisodeBriefSection />

      {/* 감수 패스 — 단일 생성에서만 기존 감수·수정본 흐름을 사용한다 */}
      {generationMode === 'single' && (
      <section className="rounded-md border border-border p-3">
        <h3 className="mb-2 text-xs font-semibold text-muted-foreground">감수 패스</h3>
        <Checkbox
          label="생성 후 자동 감수 (지적 + 수정본)"
          checked={reviewPass}
          onChange={(e) => setReviewPass(e.target.checked)}
        />
        {reviewPass && (
          <div className="mt-2">
            <Label htmlFor="ai-review-effort">감수 추론 강도</Label>
            <Select
              id="ai-review-effort"
              value={reviewEffort}
              onChange={(e) => setReviewEffort(e.target.value as AiPanelState['reviewEffort'])}
            >
              <option value="">엔드포인트 설정값 사용</option>
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
              <option value="xhigh">xhigh</option>
            </Select>
            <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
              초안 응답이 끝나면 같은 스트림에서 감수 의견과 수정 원고를 이어 생성합니다. 감수만 실패해도 초안은 보존됩니다.
            </p>
          </div>
        )}
      </section>
      )}

      {/* 포함 컨텍스트 */}
      <ContextSection ctx={ctx} setContext={setContext} />

      <div className="flex items-center gap-2">
        {/* 로딩 중에도 막지 않는다 — 클릭 시 안내 후 자동 재시도. 실제 등록된 엔드포인트가 없을 때만 비활성 */}
        {status === 'streaming' ? (
          <Button variant="outline" size="sm" onClick={stop}>⏹ 중단</Button>
        ) : (
          <Button
            onClick={generate}
            disabled={endpointsQuery.isSuccess && endpoints.length === 0}
            title={pendingGenerate ? '엔드포인트 로딩 완료 후 자동 시작됩니다.' : undefined}
          >
            {pendingGenerate ? '⏳ 생성 시작 (대기 중)' : generationMode === 'parallel' ? '✨ 병렬 집필 시작' : '✨ 생성 시작'}
          </Button>
        )}
        {status === 'streaming' && (
          <>
            <Badge variant="revising" aria-live="polite">STREAMING ●</Badge>
            {generationMode === 'parallel' && (
              <span className="text-[11px] text-muted-foreground" aria-live="polite">
                {parallelProgress.phase === 'planning' && 'Planner 준비 중'}
                {parallelProgress.phase === 'workers' && `장면 ${parallelProgress.completed}/${parallelProgress.sceneCount} 조립 대기`}
                {parallelProgress.phase === 'review' && 'xhigh 전체 감수 중'}
              </span>
            )}
          </>
        )}
      </div>

      {/* 응답 (FR-405) + P1 액션 3버튼 */}
      <ResultSection />
      {error ? (
        <Alert variant="error">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}

/** FR-404 포함 컨텍스트 — 현재 회차 / 선택 캐릭터 / 선택 로어북 / 현재 장면 */
import { type AiPanelState, type EpisodeBriefState } from '@/stores/aiPanelStore';
import { SceneManager, type Scene } from '@/components/panels/SceneManager';

type AiPanelStoreApi = {
  contextSelection: AiPanelState['contextSelection'];
  setContext: (c: Partial<AiPanelState['contextSelection']>) => void;
};

function ContextSection({
  ctx,
  setContext,
}: {
  ctx: AiPanelStoreApi['contextSelection'];
  setContext: AiPanelStoreApi['setContext'];
}) {
  const chapterId = useEditorStore((s) => s.chapterId);
  const chapter = useQuery({
    queryKey: ['chapter', chapterId],
    queryFn: () => api.get<ChapterDetail>(`/chapters/${chapterId}`),
    enabled: chapterId !== null,
  });
  const scenesQuery = useQuery({
    queryKey: ['scenes', chapterId],
    queryFn: () => api.get<Scene[]>(`/chapters/${chapterId}/scenes`),
    enabled: chapterId !== null,
  });
  const scenes = scenesQuery.data ?? [];
  const includeChapter = ctx.includeChapter && ctx.chapterId !== null;
  const charsCount = ctx.characterIds.length;
  const loreCount = ctx.loreIds.length;

  // G-047 — 현재 회차 본문에 언급된 복선(키워드·제목 매칭, 서버 계산)
  const mentionedForeshadows = useQuery({
    queryKey: ['foreshadow-match', chapterId],
    queryFn: () => api.get<Array<{ id: number; title: string; status: string; audience_knows?: boolean; matched_terms: string[] }>>(
      `/projects/${chapter.data?.project_id ?? 0}/foreshadows/match?chapter_id=${chapterId}`),
    enabled: chapterId !== null,
    staleTime: 30_000,
  });

  return (
    <section className="rounded-md border border-border p-3">
      <h3 className="mb-2 flex items-center justify-between text-xs font-semibold text-muted-foreground">
        <span>포함 컨텍스트</span>
        {chapterId !== null && (
          <SceneManager
            chapterId={chapterId}
            sceneId={ctx.sceneId}
            onPick={(id) => setContext({ sceneId: id })}
          />
        )}
      </h3>
      <div className="flex flex-col gap-1.5">
        {scenes.length > 0 && (
          <div className="grid grid-cols-[auto_1fr] items-center gap-2">
            <Label htmlFor="ai-scene" className="text-xs">현재 장면</Label>
            <Select
              id="ai-scene"
              value={ctx.sceneId ?? ''}
              onChange={(e) =>
                setContext({ sceneId: e.target.value === '' ? null : Number(e.target.value) })}
            >
              <option value="">사용 안 함 (회차 전체)</option>
              {scenes.map((s) => (
                <option key={s.id} value={s.id}>{s.title || '무제'}</option>
              ))}
            </Select>
          </div>
        )}
        <Checkbox
          label={`현재 회차${chapter.data ? ` (${chapter.data.title.trim() || `${volumeLabel(chapter.data.volume)} ${chapter.data.id}화`})` : ''}`}
          checked={includeChapter}
          disabled={chapterId === null}
          onChange={(e) => setContext({ includeChapter: e.target.checked })}
        />
        <Checkbox
          label={`선택 캐릭터 (${charsCount})`}
          checked={ctx.includeCharacters && charsCount > 0}
          disabled={charsCount === 0}
          onChange={(e) => setContext({ includeCharacters: e.target.checked })}
        />
        <Checkbox
          label={`선택 로어북 (${loreCount})`}
          checked={ctx.includeLore && loreCount > 0}
          disabled={loreCount === 0}
          onChange={(e) => setContext({ includeLore: e.target.checked })}
        />
        <Checkbox
          label="세계관 자동 포함 (본문 키워드 매칭)"
          checked={ctx.autoLore}
          disabled={chapterId === null}
          onChange={(e) => setContext({ autoLore: e.target.checked })}
        />
        <Checkbox
          label="시맨틱 매칭 강화 (형태소 변형·대명사 지칭 보완)"
          checked={ctx.autoLoreSemantic}
          disabled={chapterId === null || !ctx.autoLore}
          onChange={(e) => setContext({ autoLoreSemantic: e.target.checked })}
        />
        <Checkbox
          label="목차 자동 포함 (시놉시스·다음 화 방향)"
          checked={ctx.autoOutline}
          disabled={chapterId === null}
          onChange={(e) => setContext({ autoOutline: e.target.checked })}
        />
        <Checkbox
          label="미회수 복선 자동 포함"
          checked={ctx.autoForeshadow}
          disabled={chapterId === null}
          onChange={(e) => setContext({ autoForeshadow: e.target.checked })}
        />
        {/* G-047 — 본문에 언급된 복선 안내(알림용, 자동 조치 없음) */}
        {(mentionedForeshadows.data ?? []).length > 0 && (
          <div className="flex flex-wrap items-center gap-1">
            <span className="text-[10px] text-muted-foreground">이 회차 본문에서 건드리는 복선:</span>
            {(mentionedForeshadows.data ?? []).map((m) => (
              <Badge
                key={m.id}
                variant={m.status === '회수' ? 'done' : 'revising'}
                className="text-[10px]"
                title={`상태: ${m.status}${m.audience_knows ? ' · 독자 인지' : ''} — 매칭: ${m.matched_terms.join(', ')}`}
              >
                {m.title}
              </Badge>
            ))}
          </div>
        )}
        <Checkbox
          label="문체 프로파일 적용 (기획 페이지에서 편집)"
          checked={ctx.styleProfile}
          onChange={(e) => setContext({ styleProfile: e.target.checked })}
        />
      </div>
      <InjectedBadges ctx={ctx} />
    </section>
  );
}

/** 이번 화 브리프 — 선택적 생성 계약 입력. 필수 항목이 비면 brief 없이 생성된다. */
function EpisodeBriefSection() {
  const [open, setOpen] = useState(false);
  const brief = useAiPanelStore((s) => s.episodeBrief);
  const setBrief = useAiPanelStore((s) => s.setEpisodeBrief);
  // 브리프 필수값이 모두 유효해 실제로 전송되는 상태 — 배지로 항상 공개한다(NFR-201)
  const applying = parseEpisodeBrief(brief).ok;
  return (
    <section className="rounded-md border border-border p-3">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-xs font-semibold text-muted-foreground hover:text-foreground"
      >
        <span className="flex items-center gap-1.5">
          이번 화 브리프
          {applying && (
            <Badge variant="secondary" className="text-[10px]">이번 화 브리프 적용 중</Badge>
          )}
        </span>
        <span aria-hidden="true">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="mt-2 flex flex-col gap-2">
          <div>
            <Label htmlFor="brief-emotion-goal">감정 목표</Label>
            <Input
              id="brief-emotion-goal"
              value={brief.emotion_goal}
              onChange={(e) => setBrief({ emotion_goal: e.target.value })}
              placeholder="예: 굴욕을 뒤집는 통쾌함"
              maxLength={500}
            />
          </div>
          <div>
            <Label htmlFor="brief-core-events">핵심 사건 (한 줄에 하나, 최대 3개)</Label>
            <Textarea
              id="brief-core-events"
              rows={3}
              value={brief.core_events}
              onChange={(e) => setBrief({ core_events: e.target.value })}
              placeholder={'예: 파문 통보\n흑요검의 첫 반응'}
            />
          </div>
          <div>
            <Label htmlFor="brief-character-choices">인물 선택 (한 줄에 하나)</Label>
            <Textarea
              id="brief-character-choices"
              rows={2}
              value={brief.character_choices}
              onChange={(e) => setBrief({ character_choices: e.target.value })}
              placeholder="예: 주인공은 복귀 대신 독자 노선을 택한다"
            />
          </div>
          <div>
            <Label htmlFor="brief-cost">대가</Label>
            <Input
              id="brief-cost"
              value={brief.cost}
              onChange={(e) => setBrief({ cost: e.target.value })}
              placeholder="예: 세가 복귀 가능성을 포기한다"
              maxLength={500}
            />
          </div>
          <div>
            <Label htmlFor="brief-prohibitions">금지사항 (한 줄에 하나)</Label>
            <Textarea
              id="brief-prohibitions"
              rows={2}
              value={brief.prohibitions}
              onChange={(e) => setBrief({ prohibitions: e.target.value })}
              placeholder="예: 흑요검의 정체를 완전히 밝히지 않는다"
            />
          </div>
          <div>
            <Label htmlFor="brief-next-hook">다음 화 훅</Label>
            <Input
              id="brief-next-hook"
              value={brief.next_hook}
              onChange={(e) => setBrief({ next_hook: e.target.value })}
              placeholder="예: 검집이 열리려는 순간 뒤에서 손목을 붙잡힌다"
              maxLength={500}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label htmlFor="brief-scene-type">장면 유형</Label>
              <Select
                id="brief-scene-type"
                value={brief.scene_type}
                onChange={(e) => setBrief({ scene_type: e.target.value })}
              >
                <option value="">미지정</option>
                <option value="대립">대립</option>
                <option value="액션">액션</option>
                <option value="정보정리">정보정리</option>
                <option value="감정">감정</option>
                <option value="이동">이동</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="brief-target-chars">목표 글자 수 (선택, 1000~10000)</Label>
              <Input
                id="brief-target-chars"
                type="number"
                min={1000}
                max={10000}
                value={brief.target_chars_novelpia}
                onChange={(e) => setBrief({ target_chars_novelpia: e.target.value })}
              />
            </div>
          </div>
          <p className="text-[11px] leading-snug text-muted-foreground">
            필수 항목을 모두 채우면 브리프가 전송됩니다. 비어 있으면 브리프 없이 생성됩니다.
            항목 개수·글자 수 제한을 넘으면 경고 후 브리프 없이 생성됩니다.
            생성 결과는 자동 반영되지 않으므로 반드시 사람이 검수하세요.
          </p>
        </div>
      )}
    </section>
  );
}

/** 주입 투명성 배지 — 자동으로 곁들여진 컨텍스트를 항상 공개한다 */
function InjectedBadges({ ctx }: { ctx: AiPanelStoreApi['contextSelection'] }) {
  const injectedLore = useAiPanelStore((s) => s.injectedLore);
  const injectedForeshadows = useAiPanelStore((s) => s.injectedForeshadows);
  const injectedOutline = useAiPanelStore((s) => s.injectedOutline);
  const chips: string[] = [];
  if (ctx.sceneId) chips.push('선택 장면');
  if (injectedOutline?.current) chips.push('이번 화 목표');
  if (injectedOutline?.next_title) chips.push(`다음 화: ${injectedOutline.next_title}`);
  for (const l of injectedLore) chips.push(`세계관: ${l.title}`);
  for (const f of injectedForeshadows) chips.push(`복선: ${f.title}`);
  if (chips.length === 0) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-1" aria-label="자동 주입된 컨텍스트">
      {chips.map((c, i) => (
        <Badge key={`${c}-${i}`} variant="secondary" className="text-[10px]">{c}</Badge>
      ))}
    </div>
  );
}

/** 응답 영역(초안/감수 의견/수정본 탭) + [끼워넣기][선택 교체][복사] — FR-406의 유일한 반영 경로 */
type ResultTab = AiPanelState['resultTab'];

function ResultSection() {
  const status = useAiPanelStore((s) => s.status);
  const streamingText = useAiPanelStore((s) => s.streamingText);
  const reviewText = useAiPanelStore((s) => s.reviewText);
  const refinedText = useAiPanelStore((s) => s.refinedText);
  const resultTab = useAiPanelStore((s) => s.resultTab);
  const setResultTab = useAiPanelStore((s) => s.setResultTab);
  const reviewInfo = useAiPanelStore((s) => s.reviewInfo);
  const scrollRef = useRef<HTMLDivElement>(null);

  const hasReview = reviewText.length > 0 || refinedText.length > 0 || reviewInfo !== null;
  const activeText = resultTab === 'draft' ? streamingText : resultTab === 'review' ? reviewText : refinedText;

  // 자동 스크롤(sticky bottom)
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [streamingText, reviewText, refinedText, resultTab]);

  /** 끼워넣기 — 현재 회차 본문 끝 append (P1 명시 클릭) */
  const insertAtEnd = useCallback(() => {
    const view = useEditorStore.getState().view;
    if (!view) {
      toast('현재 회차 에디터가 없습니다.', 'warning');
      return;
    }
    const text = activeText;
    view.dispatch({ changes: { from: view.state.doc.length, insert: '\n\n' + text } });
    view.focus();
    toast('본문 끝에 끼워넣었습니다.', 'success');
  }, [activeText]);

  /** 선택 교체 — 에디터 선택 범위만 교체, 선택 없으면 끝에 추가 */
  const replaceSelection = useCallback(() => {
    const view = useEditorStore.getState().view;
    if (!view) {
      toast('현재 회차 에디터가 없습니다.', 'warning');
      return;
    }
    const text = activeText;
    const sel = view.state.selection.main;
    const changes = sel.empty
      ? { from: view.state.doc.length, insert: '\n\n' + text }
      : { from: sel.from, to: sel.to, insert: text };
    view.dispatch({ changes });
    view.focus();
    toast(sel.empty ? '선택 범위가 없어 본문 끝에 추가했습니다.' : '선택 범위를 교체했습니다.', 'success');
  }, [activeText]);

  const copyResult = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(activeText);
      toast('클립보드에 복사했습니다.', 'success');
    } catch {
      toast('클립보드 접근이 거부되었습니다.', 'error');
    }
  }, [activeText]);

  const busy = status === 'streaming';
  const hasText = activeText.length > 0;
  // 감수 의견 탭은 본문 반영 대상이 아니다 — 복사만 허용
  const readOnlyTab = resultTab === 'review';

  const tabs: Array<{ key: ResultTab; label: string; count: number }> = [
    { key: 'draft', label: '초안', count: streamingText.length },
    { key: 'review', label: '감수 의견', count: reviewText.length },
    { key: 'refined', label: '수정본', count: refinedText.length },
  ];

  return (
    <section className="flex min-h-0 flex-col rounded-md border border-border">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <h3 className="text-xs font-semibold text-muted-foreground">
          응답 {busy ? '(스트리밍)' : ''}
        </h3>
        {reviewInfo && (
          <span className="text-[10px] text-muted-foreground" title="감수 패스 모델">
            감수: {reviewInfo.endpoint} · {reviewInfo.model}
          </span>
        )}
      </div>
      {hasReview && (
        <div className="flex gap-1 border-b border-border px-2 py-1.5" role="tablist" aria-label="응답 탭">
          {tabs.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={resultTab === t.key}
              disabled={t.count === 0 && t.key !== 'draft'}
              onClick={() => setResultTab(t.key)}
              className={
                'rounded-sm px-2 py-1 text-xs transition-colors ' +
                (resultTab === t.key
                  ? 'bg-muted font-semibold text-foreground'
                  : 'text-muted-foreground hover:text-foreground disabled:opacity-40')
              }
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
      <div ref={scrollRef} className="thin-scroll max-h-64 min-h-24 overflow-y-auto p-3">
        {hasText ? (
          <pre className="whitespace-pre-wrap break-words font-serif text-sm leading-relaxed">
            {activeText}
          </pre>
        ) : (
          <p className="text-sm text-muted-foreground">아직 응답이 없습니다.</p>
        )}
      </div>
      <div className="grid grid-cols-3 gap-1.5 border-t border-border p-2" title="결과 도착 후 활성화됩니다 (P1)">
        <Button size="sm" variant="outline" disabled={!hasText || busy || readOnlyTab} onClick={insertAtEnd}>
          ↪ 끼워넣기
        </Button>
        <Button size="sm" variant="outline" disabled={!hasText || busy || readOnlyTab} onClick={replaceSelection}>
          ⤳ 선택 교체
        </Button>
        <Button size="sm" variant="ghost" disabled={!hasText || busy} onClick={() => void copyResult()}>
          ⧉ 복사
        </Button>
      </div>
    </section>
  );
}

function ShieldCheckSlot() {
  return <ShieldCheckIcon className="mr-1 inline-block align-text-bottom text-info" />;
}
function CloudUploadSlot() {
  return <CloudUploadIcon className="mr-1 inline-block align-text-bottom text-warning" />;
}
