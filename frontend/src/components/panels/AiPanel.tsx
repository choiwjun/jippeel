/**
 * S5 AI 패널 (설계서 §2.5) — RightPanel Sheet 본체.
 *
 * P1 (FR-406): 결과는 절대 자동 삽입하지 않는다. [끼워넣기][선택 교체][복사] 3버튼만.
 * NFR-201: 상단 전송 고지 Alert 고정 — 컨텍스트 전송 사실을 매 호출 인지.
 * FR-405: fetch 스트림(SSE) 소비 — EventSource 미사용(lib/aiStream.ts).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ShieldCheckIcon, CloudUploadIcon } from "@/components/ui/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  ApiError,
  type ChapterDetail,
  type ChapterGoalOut,
  type ChapterGoalPayload,
  type ChapterGoalRevision,
  type EvidenceLinkField,
  type EvidenceLinkList,
  type PromptPreset,
  volumeLabel,
} from "@/lib/api";
import { streamGenerate, streamParallelGenerate } from "@/lib/aiStream";
import {
  EMPTY_EPISODE_BRIEF,
  useAiPanelStore,
  type AiPanelState,
  type AiResultOrigin,
  type EpisodeBriefState,
  type EpisodePurpose,
  type PendingPlan,
} from "@/stores/aiPanelStore";
import { useEditorStore } from "@/stores/editorStore";
import { flushManuscriptDraft } from "@/lib/manuscriptDrafts";
import { AiContextControls } from "@/components/editor/AiContextControls";
import { toast } from "@/components/ui/toast";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import { SceneManager, type Scene } from "@/components/panels/SceneManager";

/**
 * 회차 브리프 직렬화 — 성공 시 전송 객체, 실패 시 사유를 반환한다.
 * 'incomplete'는 필수 항목 미입력(기존 동작 유지: brief 없이 생성),
 * 'invalid'는 검증 위반(백엔드 계약 위반이므로 조용히 버리지 않고 경고 후 미전송).
 */
type ParsedBrief =
  | { ok: true; brief: Record<string, unknown> }
  | { ok: false; reason: "incomplete" }
  | { ok: false; reason: "invalid"; message: string };

function parseEpisodeBrief(
  brief: EpisodeBriefState,
  episodePurpose: EpisodePurpose = "serial",
): ParsedBrief {
  const lines = (raw: string) =>
    raw
      .split("\n")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
  const emotionGoal = brief.emotion_goal.trim();
  const coreEvents = lines(brief.core_events);
  const characterChoices = lines(brief.character_choices);
  const cost = brief.cost.trim();
  const prohibitions = lines(brief.prohibitions);
  const nextHook = brief.next_hook.trim();
  const endingIntent = brief.ending_intent.trim();
  const baseFilled =
    emotionGoal &&
    coreEvents.length > 0 &&
    characterChoices.length > 0 &&
    cost &&
    prohibitions.length > 0;
  const purposeFilled =
    episodePurpose === "serial"
      ? nextHook.length > 0
      : episodePurpose === "volume_end"
        ? nextHook.length > 0 || endingIntent.length > 0
        : endingIntent.length > 0;
  if (!baseFilled || !purposeFilled) {
    return { ok: false, reason: "incomplete" };
  }
  // 백엔드 EpisodeBrief 계약 — 위반 시 422가 되므로 전송하지 않는다
  if (coreEvents.length > 3) {
    return {
      ok: false,
      reason: "invalid",
      message: "핵심 사건은 최대 3개까지 입력할 수 있습니다.",
    };
  }
  if (characterChoices.length > 4) {
    return {
      ok: false,
      reason: "invalid",
      message: "인물 선택은 최대 4개까지 입력할 수 있습니다.",
    };
  }
  if (prohibitions.length > 10) {
    return {
      ok: false,
      reason: "invalid",
      message: "금지사항은 최대 10개까지 입력할 수 있습니다.",
    };
  }
  if (emotionGoal.length > 500) {
    return {
      ok: false,
      reason: "invalid",
      message: "감정 목표는 500자 이내로 입력하세요.",
    };
  }
  if (cost.length > 500) {
    return {
      ok: false,
      reason: "invalid",
      message: "대가는 500자 이내로 입력하세요.",
    };
  }
  if (nextHook.length > 500) {
    return {
      ok: false,
      reason: "invalid",
      message: "다음 화 훅은 500자 이내로 입력하세요.",
    };
  }
  if (endingIntent.length > 500) {
    return {
      ok: false,
      reason: "invalid",
      message: "엔딩 의도는 500자 이내로 입력하세요.",
    };
  }
  if (
    [...coreEvents, ...characterChoices, ...prohibitions].some(
      (s) => s.length > 500,
    )
  ) {
    return {
      ok: false,
      reason: "invalid",
      message: "브리프 항목 하나는 500자 이내로 입력하세요.",
    };
  }
  const target = Number(brief.target_chars_novelpia);
  if (
    brief.target_chars_novelpia !== "" &&
    (!Number.isInteger(target) || target < 1000 || target > 10000)
  ) {
    return {
      ok: false,
      reason: "invalid",
      message: "목표 글자 수는 1000~10000 사이의 정수로 입력하세요.",
    };
  }
  const out: Record<string, unknown> = {
    emotion_goal: emotionGoal,
    core_events: coreEvents,
    character_choices: characterChoices,
    cost,
    prohibitions,
  };
  if (nextHook) out.next_hook = nextHook;
  if (endingIntent) out.ending_intent = endingIntent;
  if (brief.scene_type) out.scene_type = brief.scene_type;
  if (brief.target_chars_novelpia !== "") out.target_chars_novelpia = target;
  return { ok: true, brief: out };
}

/** D01 저장용 직렬화 — 부분·빈 저장 허용(필수값 검증 없음). 서버가 동일하게 정규화한다. */
function serializeGoalPayload(brief: EpisodeBriefState): ChapterGoalPayload {
  const text = (raw: string) => (raw.trim() === "" ? null : raw.trim());
  const list = (raw: string) => {
    const items = raw
      .split("\n")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    return items.length > 0 ? items : null;
  };
  const target = Number(brief.target_chars_novelpia);
  return {
    emotion_goal: text(brief.emotion_goal),
    core_events: list(brief.core_events),
    character_choices: list(brief.character_choices),
    cost: text(brief.cost),
    prohibitions: list(brief.prohibitions),
    next_hook: text(brief.next_hook),
    ending_intent: text(brief.ending_intent),
    scene_type: brief.scene_type === "" ? null : brief.scene_type,
    target_chars_novelpia:
      brief.target_chars_novelpia !== "" && Number.isInteger(target)
        ? target
        : null,
  };
}

/** 저장본 payload → 폼 상태 (배열은 줄바꿈 원문으로 되돌린다) */
function goalToBriefState(goal: ChapterGoalPayload): EpisodeBriefState {
  const text = (v: unknown) => (typeof v === "string" ? v : "");
  const lines = (v: unknown) =>
    Array.isArray(v)
      ? v.filter((x): x is string => typeof x === "string").join("\n")
      : "";
  return {
    emotion_goal: text(goal.emotion_goal),
    core_events: lines(goal.core_events),
    character_choices: lines(goal.character_choices),
    cost: text(goal.cost),
    prohibitions: lines(goal.prohibitions),
    next_hook: text(goal.next_hook),
    ending_intent: text(goal.ending_intent),
    scene_type: text(goal.scene_type),
    target_chars_novelpia:
      goal.target_chars_novelpia == null
        ? ""
        : String(goal.target_chars_novelpia),
  };
}

const GPT_OAUTH_PROVIDER = {
  id: 0,
  name: "ChatGPT OAuth",
  default_model: "gpt-5.6-luna",
  reasoning_effort: "xhigh",
  is_default: true,
} as const;

function resultMatchesCurrentEditor(origin: AiResultOrigin | null) {
  if (!origin || origin.projectId === null || origin.chapterId === null)
    return false;
  const editor = useEditorStore.getState();
  return (
    editor.projectId === origin.projectId &&
    editor.chapterId === origin.chapterId &&
    editor.view !== null &&
    editor.saveState !== "conflict"
  );
}

export function AiPanel() {
  // 폼 상태
  const presetId = useAiPanelStore((s) => s.presetId);
  const setPreset = useAiPanelStore((s) => s.setPreset);
  const promptOverride = useAiPanelStore((s) => s.promptOverride);
  const setPrompt = useAiPanelStore((s) => s.setPrompt);
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
  const parallelReviewEffort = useAiPanelStore((s) => s.parallelReviewEffort);
  const setParallelReviewEffort = useAiPanelStore(
    (s) => s.setParallelReviewEffort,
  );
  const parallelProgress = useAiPanelStore((s) => s.parallelProgress);

  // 컨텍스트 + 스트리밍
  const ctx = useAiPanelStore((s) => s.contextSelection);
  const setContext = useAiPanelStore((s) => s.setContext);
  const pendingGenerate = useAiPanelStore((s) => s.pendingGenerate);
  const status = useAiPanelStore((s) => s.status);
  const error = useAiPanelStore((s) => s.error);
  const pendingPlan = useAiPanelStore((s) => s.pendingPlan);
  const planBusy = useAiPanelStore((s) => s.planBusy);

  // 서버 데이터 — provider 선택/모델 목록 API 없이 고정 OAuth 계정을 사용한다.
  const presetsQuery = useQuery({
    queryKey: ["ai-presets"],
    queryFn: () => api.get<PromptPreset[]>("/ai/presets"),
  });

  const selectedPreset = useMemo(
    () => (presetsQuery.data ?? []).find((p) => p.id === presetId) ?? null,
    [presetsQuery.data, presetId],
  );

  /**
   * 스트림 제어 — abort 소유권은 aiPanelStore(모듈 스코프)로 이전.
   * 언마운트 클린업 없음: 쿼리 settle 등으로 인한 재마운트가 스트림을 죽이지 않는다.
   * 패널 의도적 닫힘(close/toggle-off) 시에만 store.close()가 abort한다.
   */
  /**
   * 공통 전처리 — 프리셋/프롬프트 검사, 편집기 바인딩·revision 앵커,
   * directives·브리프·컨텍스트 조립. 생성과 계획 요청이 같은 경로를 쓴다.
   * 실패 시 null을 반환하고 시작 토큰은 여기서 해제한다.
   */
  const prepareRequest = useCallback(async () => {
      const store = useAiPanelStore.getState();
      if (!store.presetId && !store.promptOverride.trim()) {
        toast("프리셋을 고르거나 프롬프트를 입력하세요.", "warning");
        return null;
      }
      const startToken = store.reserveAiStart("generate");
      if (startToken === null) return null;

      const editorBefore = useEditorStore.getState();
      const c = structuredClone(store.contextSelection);
      const activeEditorIdentity = store.activeEditorIdentity
        ? structuredClone(store.activeEditorIdentity)
        : null;
      const editorIntent = c.requestSource === "editor";
      let expectedRevision: number | null = null;
      let boundProjectId = c.projectId;
      let boundChapterId = editorIntent ? c.chapterId : null;

      if (editorIntent) {
        if (
          c.projectId === null ||
          c.chapterId === null ||
          activeEditorIdentity === null ||
          activeEditorIdentity.projectId !== c.projectId ||
          activeEditorIdentity.chapterId !== c.chapterId ||
          editorBefore.projectId !== c.projectId ||
          editorBefore.chapterId !== c.chapterId
        ) {
          toast(
            "현재 열려 있는 회차를 확인할 수 없어 AI 요청을 시작하지 않았습니다.",
            "warning",
          );
          useAiPanelStore.getState().clearAiStart(startToken);
          return null;
        }
        boundProjectId = c.projectId;
        boundChapterId = c.chapterId;
      }

      const directives = structuredClone(
        store.getDirectives(boundProjectId, boundChapterId),
      );
      const parsedBrief = parseEpisodeBrief(
        structuredClone(store.episodeBrief),
        directives.episodePurpose,
      );
      if (!parsedBrief.ok && parsedBrief.reason === "invalid") {
        toast(`브리프를 전송하지 않습니다 — ${parsedBrief.message}`, "warning");
      }
      const brief = parsedBrief.ok ? structuredClone(parsedBrief.brief) : null;
      const settingsSnapshot = {
        generationMode: store.generationMode,
        presetId: store.presetId,
        promptOverride: store.promptOverride.trim(),
        maxTokens: store.maxTokens,
        reviewPass: store.reviewPass,
        reviewEffort: store.reviewEffort,
        workerLimit: store.workerLimit,
        parallelReviewEffort: store.parallelReviewEffort,
      };
      if (editorIntent && boundProjectId !== null && boundChapterId !== null) {
        let flushed;
        try {
          flushed = await flushManuscriptDraft(boundProjectId, boundChapterId);
        } catch (e) {
          toast((e as Error).message, "error");
          useAiPanelStore.getState().clearAiStart(startToken);
          return null;
        }
        const after = useEditorStore.getState();
        const activeAfter = useAiPanelStore.getState().activeEditorIdentity;
        if (
          !useAiPanelStore.getState().isAiStartCurrent(startToken) ||
          activeAfter === null ||
          activeAfter.projectId !== boundProjectId ||
          activeAfter.chapterId !== boundChapterId ||
          after.projectId !== boundProjectId ||
          after.chapterId !== boundChapterId
        ) {
          if (useAiPanelStore.getState().isAiStartCurrent(startToken)) {
            useAiPanelStore.getState().clearAiStart(startToken);
          }
          toast("회차가 바뀌어 AI 요청을 시작하지 않았습니다.", "warning");
          return null;
        }
        expectedRevision = flushed.detail.revision;
        boundProjectId = flushed.detail.project_id;
        boundChapterId = flushed.detail.id;
      }

      if (!useAiPanelStore.getState().isAiStartCurrent(startToken)) return null;
      const base = {
        preset_id: settingsSnapshot.presetId,
        prompt_override: settingsSnapshot.promptOverride || null,
        context: {
          project_id: boundProjectId,
          chapter_id: boundChapterId,
          include_chapter_content: editorIntent
            ? c.includeChapterContent
            : false,
          expected_revision: expectedRevision,
          episode_purpose: directives.episodePurpose,
          approved_foreshadow_ids: directives.approvedForeshadowIds,
          include_relationships:
            directives.includeRelationships &&
            c.includeCharacters &&
            c.characterIds.length >= 2,
          character_ids: c.includeCharacters ? [...c.characterIds] : [],
          lore_ids: c.includeLore ? [...c.loreIds] : [],
          auto_lore: c.autoLore,
          auto_lore_semantic: c.autoLoreSemantic,
          auto_outline: c.autoOutline,
          auto_foreshadow: c.autoForeshadow,
          scene_id: editorIntent ? c.sceneId : null,
          style_profile: c.styleProfile,
          // 계획 경로와 같은 자동 분석 — 단일 생성도 직전 회차·인물·장편 기억을 주입한다
          previous_chapter: true,
          auto_characters: true,
          include_memory: true,
          ...(brief ? { brief } : {}),
        },
        params: {
          model: GPT_OAUTH_PROVIDER.default_model,
          max_tokens: settingsSnapshot.maxTokens,
        },
      };
      return {
        startToken,
        base,
        boundProjectId,
        boundChapterId,
        expectedRevision,
        includeChapterContent: editorIntent ? c.includeChapterContent : false,
        settingsSnapshot,
      };
  }, []);

  /** P2 — [수락하고 집필]: 승인된 계획을 planner 재호출 없이 실행한다 */
  const generate = useCallback(
    (approved?: { plan: PendingPlan["plan"]; planOutputId: number | null }) => {
    void (async () => {
      const prep = await prepareRequest();
      if (!prep) return;
      const {
        startToken,
        base,
        boundProjectId,
        boundChapterId,
        expectedRevision,
        includeChapterContent,
        settingsSnapshot,
      } = prep;
      const parallel = settingsSnapshot.generationMode === "parallel";
      const body = {
        ...base,
        // 승인된 계획과 같은 컨텍스트로 집필한다 — 계획은 자동 분석을 전제로 한다
        ...(approved
          ? {
              context: {
                ...base.context,
                previous_chapter: true,
                auto_lore: true,
                auto_lore_semantic: true,
                auto_outline: true,
                auto_foreshadow: true,
                style_profile: true,
                include_memory: true,
                auto_characters: true,
                include_relationships: true,
              },
            }
          : {}),
        ...(parallel
          ? {
              worker_limit: settingsSnapshot.workerLimit,
              generation_reasoning_effort: "medium",
              review: {
                model: GPT_OAUTH_PROVIDER.default_model,
                reasoning_effort:
                  settingsSnapshot.parallelReviewEffort || "xhigh",
              },
              ...(approved
                ? {
                    approved_plan: approved.plan,
                    plan_output_id: approved.planOutputId,
                  }
                : {}),
            }
          : {
              review: settingsSnapshot.reviewPass
                ? {
                    reasoning_effort:
                      settingsSnapshot.reviewEffort || undefined,
                  }
                : null,
              ...(approved
                ? {
                    approved_plan: approved.plan,
                    plan_output_id: approved.planOutputId,
                  }
                : {}),
            }),
      };
      useAiPanelStore.getState().startStream({
        projectId: boundProjectId,
        chapterId: boundChapterId,
        expectedRevision,
        includeChapterContent,
        startedAt: Date.now(),
      });
      const stream = parallel ? streamParallelGenerate : streamGenerate;
      useAiPanelStore.getState().setAbort(
        stream(body, {
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
            st.setParallelProgress({
              phase: "planning",
              sceneCount: 0,
              started: 0,
              completed: 0,
              workerLimit: info.workerLimit,
            });
          },
          onPlannerDone: (info) =>
            useAiPanelStore.getState().setParallelProgress({
              phase: "workers",
              sceneCount: info.sceneCount,
              started: 0,
              completed: 0,
            }),
          onWorkerStart: () => {
            const st = useAiPanelStore.getState();
            st.setParallelProgress({
              started: st.parallelProgress.started + 1,
            });
          },
          onWorkerDone: () => {
            const st = useAiPanelStore.getState();
            st.setParallelProgress({
              completed: st.parallelProgress.completed + 1,
            });
          },
          onReviewStart: (info) => {
            const st = useAiPanelStore.getState();
            st.setReviewInfo({ model: info.model, provider: info.provider });
            st.setParallelProgress({ phase: "review" });
            if (st.resultTab !== "review") st.setResultTab("review");
          },
          onReviewChunk: (d) => useAiPanelStore.getState().appendReviewChunk(d),
          onRefinedChunk: (d) => {
            const st = useAiPanelStore.getState();
            if (st.resultTab !== "refined") st.setResultTab("refined");
            st.appendRefinedChunk(d);
          },
          onReviewError: (msg) => toast(msg, "warning"),
          onGenerationSaved: (info) =>
            useAiPanelStore.getState().setGenerationSaved(info),
          onParallelError: (msg, stage) => {
            if (stage === "generation")
              useAiPanelStore.getState().failStream(msg);
            toast(msg, stage === "review" ? "warning" : "error");
          },
          onDone: () => {
            if (useAiPanelStore.getState().status === "streaming") {
              useAiPanelStore.getState().finishStream();
            }
          },
          onError: (msg) => {
            useAiPanelStore.getState().failStream(msg);
            toast(msg, "error");
          },
        }),
      );
      useAiPanelStore.getState().clearAiStart(startToken);
    })();
    },
    [prepareRequest],
  );

  /**
   * P1 — [계획 보기]: 컨텍스트를 분석해 장면 계획만 받는다. 원고는 쓰지 않고
   * pendingPlan에 보관해 작가가 전체를 한 번에 검토하게 한다.
   */
  const requestPlan = useCallback(() => {
    void (async () => {
      const prep = await prepareRequest();
      if (!prep) return;
      const st = useAiPanelStore.getState();
      st.setPlanBusy(true);
      st.setPlanError(null);
      st.setPendingPlan(null);
      try {
        // 어시스턴트 계획은 설정·인물·로어·복선·이전 회차·문체·회차 목표를
        // 자동 분석한다 — 세부 선택을 일일이 고르지 않아도 된다.
        const res = await api.post<{
          run_id: number | null;
          plan_output_id: number | null;
          plan: PendingPlan["plan"];
          chapter_revision: number | null;
          episode_purpose: string;
        }>("/ai/plan", {
          ...prep.base,
          generation_reasoning_effort: "medium",
          context: {
            ...prep.base.context,
            previous_chapter: true,
            auto_lore: true,
            auto_lore_semantic: true,
            auto_outline: true,
            auto_foreshadow: true,
            style_profile: true,
            include_memory: true,
            auto_characters: true,
            include_relationships: true,
          },
        });
        st.setPendingPlan({
          runId: res.run_id,
          planOutputId: res.plan_output_id,
          chapterRevision: res.chapter_revision,
          plan: res.plan,
        });
      } catch (e) {
        const msg = (e as Error).message;
        st.setPlanError(msg);
        toast(msg, "error");
      } finally {
        st.setPlanBusy(false);
        useAiPanelStore.getState().clearAiStart(prep.startToken);
      }
    })();
  }, [prepareRequest]);

  // provider 로딩을 기다릴 필요가 없으므로 과거 pending 플래그만 정리한다.
  useEffect(() => {
    if (!pendingGenerate) return;
    useAiPanelStore.getState().setPendingGenerate(false);
    generate();
  }, [generate, pendingGenerate]);

  const stop = useCallback(() => {
    const st = useAiPanelStore.getState();
    st.clearAiStart();
    st.abortStream();
    if (useAiPanelStore.getState().status === "streaming") {
      useAiPanelStore.getState().finishStream();
    }
  }, []);

  return (
    <div className="flex flex-col gap-3">
      {/* P1 가드 (FR-406) */}
      <Alert variant="info">
        <ShieldCheckSlot />
        <AlertDescription>
          AI 결과는 자동으로 본문에 들어가지 않습니다. ‘끼워넣기’ 또는 ‘선택
          교체’를 눌러야 반영됩니다.
        </AlertDescription>
      </Alert>
      {/* NFR-201 전송 고지 (M-2) — 브리프 포함 */}
      <Alert variant="warning">
        <CloudUploadSlot />
        <AlertDescription>
          선택한 회차·카드·로어북·이번 화 브리프 내용은 ChatGPT OAuth 브릿지로
          전송됩니다.
        </AlertDescription>
      </Alert>

      {/* 호출 컨텍스트 (FR-401/407) */}
      <section className="rounded-md border border-border p-3">
        <h3 className="mb-2 text-xs font-semibold text-muted-foreground">
          호출 컨텍스트
        </h3>
        <div className="grid grid-cols-2 gap-2">
          <div className="col-span-2 rounded-sm bg-muted px-2 py-2">
            <p className="text-xs font-medium">AI 계정: ChatGPT OAuth</p>
            <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
              로컬 OAuth 브릿지가 관리하는 ChatGPT 계정으로 집필합니다. API
              key나 서버 주소를 입력하지 않습니다.
            </p>
          </div>
          <div className="col-span-2 rounded-sm border border-dashed border-border px-2 py-2">
            <p className="text-xs font-medium">
              고정 모델: {GPT_OAUTH_PROVIDER.default_model}
            </p>
            <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
              reasoning 모델 계약상 temperature는 지원하지 않으며 요청에
              전송하지 않습니다.
            </p>
          </div>
          <div>
            <Label htmlFor="ai-maxtok">
              max_tokens {maxTokens.toLocaleString()}
            </Label>
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
        <h3 className="mb-2 text-xs font-semibold text-muted-foreground">
          프롬프트
        </h3>
        <Label htmlFor="ai-preset">프리셋</Label>
        <Select
          id="ai-preset"
          className="mb-2"
          value={presetId ?? ""}
          onChange={(e) =>
            setPreset(e.target.value === "" ? null : Number(e.target.value))
          }
        >
          <option value="">직접 입력</option>
          {(presetsQuery.data ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </Select>
        {selectedPreset && (
          <p className="mb-2 rounded-sm bg-muted px-2 py-1.5 text-[11px] leading-snug text-muted-foreground">
            <span className="font-medium text-foreground">
              {selectedPreset.name}:{" "}
            </span>
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
        <h3 className="mb-2 text-xs font-semibold text-muted-foreground">
          생성 엔진
        </h3>
        <Label htmlFor="ai-generation-mode">집필 모드</Label>
        <Select
          id="ai-generation-mode"
          value={generationMode}
          onChange={(e) =>
            setGenerationMode(e.target.value as "single" | "parallel")
          }
        >
          <option value="single">단일 생성 (기존 흐름)</option>
          <option value="parallel">병렬 장면 집필 + 전체 감수</option>
        </Select>
        {generationMode === "parallel" && (
          <div className="mt-2 space-y-2">
            <div>
              <Label htmlFor="ai-worker-limit">
                동시 장면 수: {workerLimit}
              </Label>
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
              <p className="text-xs font-medium">전체 감수: ChatGPT OAuth</p>
              <p className="mt-2 text-xs font-medium">
                감수 모델: {GPT_OAUTH_PROVIDER.default_model}
              </p>
              <Label className="mt-2 block" htmlFor="ai-parallel-review-effort">
                감수 추론 강도
              </Label>
              <Select
                id="ai-parallel-review-effort"
                value={parallelReviewEffort}
                onChange={(e) =>
                  setParallelReviewEffort(
                    e.target.value as AiPanelState["parallelReviewEffort"],
                  )
                }
              >
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
                <option value="xhigh">xhigh (권장)</option>
              </Select>
              <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
                Planner·장면 worker·전체 감수는 모두 같은 ChatGPT OAuth 계정을
                사용합니다.
              </p>
            </div>
          </div>
        )}
      </section>

      {/* 이번 화 브리프 — 필수 항목이 모두 채워졌을 때만 context.brief로 전송 */}
      <EpisodeBriefSection />

      {/* 감수 패스 — 단일 생성에서만 기존 감수·수정본 흐름을 사용한다 */}
      {generationMode === "single" && (
        <section className="rounded-md border border-border p-3">
          <h3 className="mb-2 text-xs font-semibold text-muted-foreground">
            감수 패스
          </h3>
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
                onChange={(e) =>
                  setReviewEffort(
                    e.target.value as AiPanelState["reviewEffort"],
                  )
                }
              >
                <option value="">GPT OAuth 기본값 사용</option>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
                <option value="xhigh">xhigh</option>
              </Select>
              <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
                초안 응답이 끝나면 같은 스트림에서 감수 의견과 수정 원고를 이어
                생성합니다. 감수만 실패해도 초안은 보존됩니다.
              </p>
            </div>
          )}
        </section>
      )}

      {/* 포함 컨텍스트 */}
      <ContextSection ctx={ctx} setContext={setContext} />

      <div className="flex items-center gap-2">
        {/* 로딩 중에도 막지 않는다 — 클릭 시 안내 후 자동 재시도. */}
        {status === "streaming" ? (
          <Button variant="outline" size="sm" onClick={stop}>
            ⏹ 중단
          </Button>
        ) : (
          <>
            {/* 어시스턴트 기본 경로 — 계획을 먼저 만들어 한 번에 검토한다 */}
            <Button
              onClick={requestPlan}
              disabled={planBusy}
              title="설정·인물·로어·복선·이전 회차·문체·회차 목표를 자동 분석해 집필 계획을 먼저 보여줍니다."
            >
              {pendingGenerate || planBusy
                ? "⏳ 계획 준비 중"
                : "🗺 계획 만들기"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => generate()}
              title="계획 검토 없이 곧바로 집필합니다."
            >
              바로 생성
            </Button>
          </>
        )}
        {status === "streaming" && (
          <>
            <Badge variant="revising" aria-live="polite">
              STREAMING ●
            </Badge>
            {generationMode === "parallel" && (
              <span
                className="text-[11px] text-muted-foreground"
                aria-live="polite"
              >
                {parallelProgress.phase === "planning" && "Planner 준비 중"}
                {parallelProgress.phase === "workers" &&
                  `장면 ${parallelProgress.completed}/${parallelProgress.sceneCount} 조립 대기`}
                {parallelProgress.phase === "review" && "xhigh 전체 감수 중"}
              </span>
            )}
          </>
        )}
      </div>

      {/* P1 — 계획 검토 카드: 승인 전까지 원고를 쓰지 않는다 */}
      {pendingPlan && (
        <PlanReviewCard
          plan={pendingPlan}
          busy={status === "streaming" || planBusy}
          onAccept={() => {
            const p = pendingPlan;
            useAiPanelStore.getState().setPendingPlan(null);
            generate({ plan: p.plan, planOutputId: p.planOutputId });
          }}
          onRegenerate={requestPlan}
          onDiscard={() => useAiPanelStore.getState().setPendingPlan(null)}
        />
      )}

      {/* 응답 (FR-405) + P1 액션 3버튼 */}
      <ResultSection />
      {error ? (
        <Alert variant="error">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {/* E7 — 작가 규칙(제안→승인→적용) + 회차 생성 이력 */}
      {ctx.projectId !== null && <RulesSection projectId={ctx.projectId} />}
      {ctx.chapterId !== null && (
        <GenerationHistorySection chapterId={ctx.chapterId} />
      )}
    </div>
  );
}

/** P1 — 집필 계획 검토 카드: 승인된 계획만 generate-parallel로 집필된다 */
function PlanReviewCard({
  plan,
  busy,
  onAccept,
  onRegenerate,
  onDiscard,
}: {
  plan: PendingPlan;
  busy: boolean;
  onAccept: () => void;
  onRegenerate: () => void;
  onDiscard: () => void;
}) {
  return (
    <section
      className="rounded-md border border-border p-3"
      aria-label="집필 계획 검토"
    >
      <h3 className="mb-2 text-xs font-semibold text-muted-foreground">
        집필 계획 — {plan.plan.scenes.length}개 장면
      </h3>
      <p className="mb-2 text-[11px] leading-snug text-muted-foreground">
        계획은 아직 원고가 아닙니다. [수락하고 집필]을 눌러야 이 계획대로
        병렬 집필이 시작되고, [폐기]는 아무것도 반영하지 않습니다.
      </p>
      <ol className="flex flex-col gap-2">
        {plan.plan.scenes.map((scene) => (
          <li
            key={scene.order}
            className="rounded-sm bg-muted px-2 py-2"
          >
            <p className="text-xs font-medium">
              {scene.order}. {scene.title}
            </p>
            <dl className="mt-1 grid grid-cols-[4.5rem_1fr] gap-x-2 gap-y-0.5 text-[11px] leading-snug">
              <dt className="text-muted-foreground">목적</dt>
              <dd>{scene.purpose}</dd>
              <dt className="text-muted-foreground">목표</dt>
              <dd>{scene.objective}</dd>
              <dt className="text-muted-foreground">선택</dt>
              <dd>{scene.choice}</dd>
              <dt className="text-muted-foreground">대가</dt>
              <dd>{scene.cost}</dd>
              <dt className="text-muted-foreground">비트</dt>
              <dd>{scene.required_beats.join(" → ")}</dd>
              <dt className="text-muted-foreground">인물</dt>
              <dd>{scene.characters.join(", ")}</dd>
              <dt className="text-muted-foreground">시작 상태</dt>
              <dd>{scene.opening_state}</dd>
              {scene.closing_hook ? (
                <>
                  <dt className="text-muted-foreground">훅</dt>
                  <dd>{scene.closing_hook}</dd>
                </>
              ) : null}
              {scene.ending_intent ? (
                <>
                  <dt className="text-muted-foreground">결말 의도</dt>
                  <dd>{scene.ending_intent}</dd>
                </>
              ) : null}
            </dl>
          </li>
        ))}
      </ol>
      <div className="mt-3 flex items-center gap-2">
        <Button size="sm" onClick={onAccept} disabled={busy}>
          ✅ 수락하고 집필
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onRegenerate}
          disabled={busy}
        >
          다시 생성
        </Button>
        <Button variant="ghost" size="sm" onClick={onDiscard} disabled={busy}>
          폐기
        </Button>
      </div>
    </section>
  );
}

/** FR-404 포함 컨텍스트 — 현재 회차 / 선택 캐릭터 / 선택 로어북 / 현재 장면 */

type AiPanelStoreApi = {
  contextSelection: AiPanelState["contextSelection"];
  setContext: (c: Partial<AiPanelState["contextSelection"]>) => void;
};

function ContextSection({
  ctx,
  setContext,
}: {
  ctx: AiPanelStoreApi["contextSelection"];
  setContext: AiPanelStoreApi["setContext"];
}) {
  const chapterId = ctx.chapterId;
  const chapter = useQuery({
    queryKey: ["chapter", chapterId],
    queryFn: () => api.get<ChapterDetail>(`/chapters/${chapterId}`),
    enabled: chapterId !== null,
  });
  const scenesQuery = useQuery({
    queryKey: ["scenes", chapterId],
    queryFn: () => api.get<Scene[]>(`/chapters/${chapterId}/scenes`),
    enabled: chapterId !== null,
  });
  const scenes = scenesQuery.data ?? [];
  const includeChapter = ctx.includeChapterContent && ctx.chapterId !== null;
  const charsCount = ctx.characterIds.length;
  const loreCount = ctx.loreIds.length;

  // G-047 — 현재 회차 본문에 언급된 복선(키워드·제목 매칭, 서버 계산)
  const mentionedForeshadows = useQuery({
    queryKey: ["foreshadow-match", chapterId],
    queryFn: () =>
      api.get<
        Array<{
          id: number;
          title: string;
          status: string;
          audience_knows?: boolean;
          matched_terms: string[];
        }>
      >(
        `/projects/${chapter.data?.project_id ?? 0}/foreshadows/match?chapter_id=${chapterId}`,
      ),
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
            <Label htmlFor="ai-scene" className="text-xs">
              현재 장면
            </Label>
            <Select
              id="ai-scene"
              value={ctx.sceneId ?? ""}
              onChange={(e) =>
                setContext({
                  sceneId:
                    e.target.value === "" ? null : Number(e.target.value),
                })
              }
            >
              <option value="">사용 안 함 (회차 전체)</option>
              {scenes.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title || "무제"}
                </option>
              ))}
            </Select>
          </div>
        )}
        <Checkbox
          label={`현재 회차 본문 포함${chapter.data ? ` (${chapter.data.title.trim() || `${volumeLabel(chapter.data.volume)} ${chapter.data.id}화`})` : ""}`}
          checked={includeChapter}
          disabled={chapterId === null}
          onChange={(e) =>
            setContext({
              includeChapterContent: e.target.checked,
              includeChapter: e.target.checked,
            })
          }
        />
        <AiContextControls
          projectId={ctx.projectId}
          chapterId={ctx.chapterId}
          relationshipPolicy={{
            kind: "generation",
            selectedCharacterCount: ctx.characterIds.length,
          }}
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
            <span className="text-[10px] text-muted-foreground">
              이 회차 본문에서 건드리는 복선:
            </span>
            {(mentionedForeshadows.data ?? []).map((m) => (
              <Badge
                key={m.id}
                variant={m.status === "회수" ? "done" : "revising"}
                className="text-[10px]"
                title={`상태: ${m.status}${m.audience_knows ? " · 독자 인지" : ""} — 매칭: ${m.matched_terms.join(", ")}`}
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

/** 이번 화 브리프 — 선택적 생성 계약 입력 + D01 회차 목표 영속화. */
function EpisodeBriefSection() {
  const [open, setOpen] = useState(false);
  const brief = useAiPanelStore((s) => s.episodeBrief);
  const setBrief = useAiPanelStore((s) => s.setEpisodeBrief);
  const ctx = useAiPanelStore((s) => s.contextSelection);
  const episodePurpose = useAiPanelStore(
    (s) => s.getDirectives(ctx.projectId, ctx.chapterId).episodePurpose,
  );
  // 브리프 필수값이 모두 유효해 실제로 전송되는 상태 — 배지로 항상 공개한다(NFR-201)
  const applying = parseEpisodeBrief(brief, episodePurpose).ok;
  // D01 — 저장된 목표는 dirty가 아닐 때만 폼에 적재하고, 저장 purpose를 되돌린다.
  const goalQuery = useChapterGoal();
  useEffect(() => {
    const data = goalQuery.data;
    if (!data?.goal) return;
    const st = useAiPanelStore.getState();
    // 늦은 응답 격리 — 응답 회차가 현재 회차와 다르거나 사용자 입력이 있으면 덮지 않는다
    if (st.contextSelection.chapterId !== data.chapter_id || st._briefDirty)
      return;
    st.hydrateEpisodeBrief(
      data.project_id,
      data.chapter_id,
      goalToBriefState(data.goal.goal),
    );
    st.setDirectives(data.project_id, data.chapter_id, {
      episodePurpose: data.goal.episode_purpose,
    });
  }, [goalQuery.data]);
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
            <Badge variant="secondary" className="text-[10px]">
              이번 화 브리프 적용 중
            </Badge>
          )}
          <GoalSavedBadge />
        </span>
        <span aria-hidden="true">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="mt-2 flex flex-col gap-2">
          <ChapterGoalControls episodePurpose={episodePurpose} />
          <EvidenceLinksSection />
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
            <Label htmlFor="brief-core-events">
              핵심 사건 (한 줄에 하나, 최대 3개)
            </Label>
            <Textarea
              id="brief-core-events"
              rows={3}
              value={brief.core_events}
              onChange={(e) => setBrief({ core_events: e.target.value })}
              placeholder={"예: 파문 통보\n흑요검의 첫 반응"}
            />
          </div>
          <div>
            <Label htmlFor="brief-character-choices">
              인물 선택 (한 줄에 하나)
            </Label>
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
              placeholder={
                episodePurpose === "series_finale"
                  ? "선택: 후일담 단서가 있을 때만 입력"
                  : "예: 검집이 열리려는 순간 뒤에서 손목을 붙잡힌다"
              }
              maxLength={500}
            />
          </div>
          <div>
            <Label htmlFor="brief-ending-intent">엔딩 의도</Label>
            <Input
              id="brief-ending-intent"
              value={brief.ending_intent}
              onChange={(e) => setBrief({ ending_intent: e.target.value })}
              placeholder="예: 두 인물이 선택의 대가를 받아들이고 끝낸다"
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
              <Label htmlFor="brief-target-chars">
                목표 글자 수 (선택, 1000~10000)
              </Label>
              <Input
                id="brief-target-chars"
                type="number"
                min={1000}
                max={10000}
                value={brief.target_chars_novelpia}
                onChange={(e) =>
                  setBrief({ target_chars_novelpia: e.target.value })
                }
              />
            </div>
          </div>
          <p className="text-[11px] leading-snug text-muted-foreground">
            연재화는 다음 화 훅, 권말은 다음 화 훅 또는 엔딩 의도, 최종화는 엔딩
            의도를 채우면 브리프가 전송됩니다. 비어 있으면 브리프 없이
            생성됩니다. 항목 개수·글자 수 제한을 넘으면 경고 후 브리프 없이
            생성됩니다. 생성 결과는 자동 반영되지 않으므로 반드시 사람이
            검수하세요.
          </p>
        </div>
      )}
    </section>
  );
}

/** D01 — 현재 회차 목표 조회. query key는 회차별로 분리한다(['chapter', id]와 별개). */
function useChapterGoal() {
  const chapterId = useAiPanelStore((s) => s.contextSelection.chapterId);
  return useQuery({
    queryKey: ["chapter-goal", chapterId],
    queryFn: () => api.get<ChapterGoalOut>(`/chapters/${chapterId}/goal`),
    enabled: chapterId !== null,
  });
}

/** 섹션 헤더 저장 상태 배지 — 저장본 vN · 기준 rM / 미저장 / 원고 변경 안내 */
function GoalSavedBadge() {
  const chapterId = useAiPanelStore((s) => s.contextSelection.chapterId);
  const goalQuery = useChapterGoal();
  if (chapterId === null) return null;
  const data = goalQuery.data;
  if (!data) return null;
  const saved = data.goal;
  if (!saved) {
    return (
      <Badge variant="outline" className="text-[10px]" aria-label="저장된 회차 목표 없음">
        미저장
      </Badge>
    );
  }
  const stale =
    saved.base_manuscript_revision !== null &&
    saved.base_manuscript_revision !== data.current_chapter_revision;
  return (
    <Badge
      variant="outline"
      className="text-[10px]"
      aria-label={`저장된 회차 목표 v${saved.goal_version}`}
      title={`목표 저장 시 본 원고 revision r${saved.base_manuscript_revision ?? "-"}`}
    >
      저장본 v{saved.goal_version} · 기준 r
      {saved.base_manuscript_revision ?? "-"}
      {stale && ` · 원고 r${data.current_chapter_revision}로 변경됨`}
    </Badge>
  );
}

/** D01 — 저장본 불러오기/저장/이력/삭제. 생성 경로는 바꾸지 않고 폼 적재만 한다. */
function ChapterGoalControls({
  episodePurpose,
}: {
  episodePurpose: EpisodePurpose;
}) {
  const ctx = useAiPanelStore((s) => s.contextSelection);
  const chapterId = ctx.chapterId;
  const projectId = ctx.projectId;
  const brief = useAiPanelStore((s) => s.episodeBrief);
  const queryClient = useQueryClient();
  const goalQuery = useChapterGoal();
  const saved = goalQuery.data?.goal ?? null;
  const historyCount = goalQuery.data?.history_count ?? 0;
  const [historyOpen, setHistoryOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const saveGoal = useMutation({
    mutationFn: (input: { form: EpisodeBriefState; expected: number | null }) =>
      api.put<ChapterGoalOut>(`/chapters/${chapterId}/goal`, {
        project_id: projectId,
        goal: serializeGoalPayload(input.form),
        episode_purpose: episodePurpose,
        expected_goal_version: input.expected,
      }),
    onSuccess: (data, vars) => {
      queryClient.setQueryData(["chapter-goal", chapterId], data);
      // D03-2: 목표 버전이 바뀌면 재개 드리프트(목표 변경됨)도 갱신 대상이다.
      void queryClient.invalidateQueries({ queryKey: ["chapter-resume", chapterId] });
      // D03-4: 목표 항목이 바뀌면 근거 링크의 drifted 판정도 갱신 대상이다.
      void queryClient.invalidateQueries({ queryKey: ["evidence-links", chapterId] });
      const st = useAiPanelStore.getState();
      const isCurrentChapter =
        st.contextSelection.chapterId === chapterId &&
        st.contextSelection.projectId === projectId;
      const formUnchanged =
        JSON.stringify(st.episodeBrief) === JSON.stringify(vars.form);
      if (!isCurrentChapter || formUnchanged)
        st.markBriefSaved(projectId, chapterId, vars.form);
      toast(
        `회차 목표를 저장했습니다 (v${data.goal?.goal_version ?? "?"}).`,
        "success",
      );
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) {
        toast(
          "목표가 다른 곳에서 먼저 저장되었습니다. 최신 목표를 확인한 뒤 다시 시도하세요.",
          "warning",
        );
        // 입력은 유지 — dirty라면 refetch hydrate가 폼을 덮지 않는다
        void queryClient.invalidateQueries({
          queryKey: ["chapter-goal", chapterId],
        });
        // 다른 곳의 목표 저장은 근거 링크 drifted 판정도 바꾼다
        void queryClient.invalidateQueries({ queryKey: ["evidence-links", chapterId] });
        return;
      }
      toast(
        e instanceof Error ? e.message : "회차 목표 저장에 실패했습니다.",
        "error",
      );
    },
  });

  const deleteGoal = useMutation({
    mutationFn: () => api.del(`/chapters/${chapterId}/goal`),
    onSuccess: () => {
      setConfirmDelete(false);
      void queryClient.invalidateQueries({
        queryKey: ["chapter-goal", chapterId],
      });
      void queryClient.invalidateQueries({ queryKey: ["chapter-resume", chapterId] });
      void queryClient.invalidateQueries({ queryKey: ["evidence-links", chapterId] });
      // 저장본 삭제 후에도 폼 입력은 유지 — dirty로 표시해 회차 전환 시 보존한다.
      const st = useAiPanelStore.getState();
      if (
        st.contextSelection.chapterId === chapterId &&
        st.contextSelection.projectId === projectId &&
        JSON.stringify(st.episodeBrief) !== JSON.stringify(EMPTY_EPISODE_BRIEF)
      )
        st.setEpisodeBrief({});
      toast("저장된 회차 목표를 삭제했습니다. 변경 이력은 보존됩니다.", "success");
    },
    onError: (e) =>
      toast(
        e instanceof Error ? e.message : "회차 목표 삭제에 실패했습니다.",
        "error",
      ),
  });

  const restoreGoal = useMutation({
    mutationFn: (goalVersion: number) =>
      api.post<ChapterGoalOut>(`/chapters/${chapterId}/goal/restore`, {
        goal_version: goalVersion,
        expected_goal_version: saved?.goal_version ?? null,
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["chapter-goal", chapterId], data);
      void queryClient.invalidateQueries({
        queryKey: ["chapter-goal-history", chapterId],
      });
      void queryClient.invalidateQueries({ queryKey: ["chapter-resume", chapterId] });
      void queryClient.invalidateQueries({ queryKey: ["evidence-links", chapterId] });
      const st = useAiPanelStore.getState();
      if (
        data.goal &&
        st.contextSelection.chapterId === data.chapter_id
      ) {
        st.loadEpisodeBrief(goalToBriefState(data.goal.goal));
        st.setDirectives(data.project_id, data.chapter_id, {
          episodePurpose: data.goal.episode_purpose,
        });
      }
      setHistoryOpen(false);
      toast(
        `목표 이력을 복원했습니다 (v${data.goal?.goal_version ?? "?"}).`,
        "success",
      );
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) {
        toast(
          "목표가 다른 곳에서 먼저 저장되었습니다. 최신 목표를 확인한 뒤 다시 시도하세요.",
          "warning",
        );
        void queryClient.invalidateQueries({
          queryKey: ["chapter-goal", chapterId],
        });
        void queryClient.invalidateQueries({ queryKey: ["evidence-links", chapterId] });
        return;
      }
      toast(
        e instanceof Error ? e.message : "목표 이력 복원에 실패했습니다.",
        "error",
      );
    },
  });

  if (chapterId === null) return null;
  return (
    <div className="flex flex-col gap-1.5 rounded-sm bg-muted/40 p-1.5">
      <div
        className="flex flex-wrap items-center gap-1.5"
        role="group"
        aria-label="회차 목표 저장"
      >
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            if (!saved) return;
            const st = useAiPanelStore.getState();
            st.loadEpisodeBrief(goalToBriefState(saved.goal));
            st.setDirectives(projectId, chapterId, {
              episodePurpose: saved.episode_purpose,
            });
          }}
          disabled={!saved}
        >
          불러오기
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() =>
            saveGoal.mutate({
              form: structuredClone(brief),
              expected: saved?.goal_version ?? null,
            })
          }
          disabled={saveGoal.isPending}
        >
          {saveGoal.isPending ? "저장 중…" : "목표 저장"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setHistoryOpen(true)}
          disabled={historyCount === 0}
        >
          이력{historyCount > 0 ? ` (${historyCount})` : ""}
        </Button>
        {confirmDelete ? (
          <span
            role="group"
            aria-label="회차 목표 삭제 확인"
            className="flex items-center gap-1 text-[11px]"
          >
            저장본을 삭제할까요? 이력은 남습니다.
            <Button
              size="sm"
              variant="destructive"
              onClick={() => deleteGoal.mutate()}
              disabled={deleteGoal.isPending}
            >
              확인
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setConfirmDelete(false)}
            >
              취소
            </Button>
          </span>
        ) : (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setConfirmDelete(true)}
            disabled={!saved}
          >
            삭제
          </Button>
        )}
      </div>
      <p className="text-[11px] leading-snug text-muted-foreground">
        목표는 회차별로 저장됩니다. 생성에는 현재 입력값이 사용되며, 저장본을
        쓰려면 불러오기로 폼에 적재하세요.
      </p>
      <GoalHistoryDialog
        open={historyOpen}
        onOpenChange={setHistoryOpen}
        chapterId={chapterId}
        currentVersion={saved?.goal_version ?? null}
        restoring={restoreGoal.isPending}
        onRestore={(v) => {
          if (
            window.confirm(
              `목표 이력 v${v}을(를) 현재 목표로 복원할까요? 새 버전으로 기록됩니다.`,
            )
          )
            restoreGoal.mutate(v);
        }}
      />
    </div>
  );
}

/** D03-4 근거 연결 — 목표 필드(사건/선택/대가) ↔ 원문 발췌의 수동 링크. */
function EvidenceLinksSection() {
  const chapterId = useAiPanelStore((s) => s.contextSelection.chapterId);
  const projectId = useAiPanelStore((s) => s.contextSelection.projectId);
  const queryClient = useQueryClient();
  const goalQuery = useChapterGoal();
  const [pick, setPick] = useState("");

  const linksQuery = useQuery({
    queryKey: ["evidence-links", chapterId],
    queryFn: () =>
      api.get<EvidenceLinkList>(`/chapters/${chapterId}/evidence-links`),
    enabled: chapterId !== null,
  });

  // 연결 가능한 목표 항목 — 저장본 기준(core_events/character_choices는 목록, cost는 스칼라)
  const goal = goalQuery.data?.goal?.goal;
  const items = useMemo(() => {
    const out: Array<{
      key: string;
      label: string;
      field: EvidenceLinkField;
      item_index: number | null;
    }> = [];
    (goal?.core_events ?? []).forEach((t, i) =>
      out.push({ key: `core_events:${i}`, label: `사건 ${i + 1} · ${t}`, field: "core_events", item_index: i }),
    );
    (goal?.character_choices ?? []).forEach((t, i) =>
      out.push({ key: `character_choices:${i}`, label: `선택 ${i + 1} · ${t}`, field: "character_choices", item_index: i }),
    );
    if (goal?.cost)
      out.push({ key: "cost", label: `대가 · ${goal.cost}`, field: "cost", item_index: null });
    return out;
  }, [goal]);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["evidence-links", chapterId] });

  const createLink = useMutation({
    mutationFn: (body: {
      goal_field: EvidenceLinkField;
      item_index: number | null;
      excerpt: string;
    }) => api.post(`/chapters/${chapterId}/evidence-links`, body),
    onSuccess: () => void invalidate(),
    onError: (e) =>
      toast(e instanceof Error ? e.message : "근거 연결에 실패했습니다.", "error"),
  });

  const deleteLink = useMutation({
    mutationFn: (lid: number) =>
      api.del(`/chapters/${chapterId}/evidence-links/${lid}`),
    onSuccess: () => void invalidate(),
    onError: (e) =>
      toast(e instanceof Error ? e.message : "근거 링크 삭제에 실패했습니다.", "error"),
  });

  if (chapterId === null) return null;
  const links = linksQuery.data?.links ?? [];
  const picked = items.find((it) => it.key === pick);

  return (
    <div
      role="group"
      className="flex flex-col gap-1.5 rounded-sm bg-muted/40 p-1.5"
      aria-label="목표 근거 연결"
    >
      <div className="text-[11px] font-medium text-muted-foreground">
        근거 연결 — 목표 항목과 본문 선택을 연결합니다(자동 판정 없음)
      </div>
      {items.length > 0 && (
        <div className="flex items-center gap-1.5">
          <Select
            aria-label="연결할 목표 항목"
            className="h-7 flex-1 text-xs"
            value={pick}
            onChange={(e) => setPick(e.target.value)}
          >
            <option value="">목표 항목 선택…</option>
            {items.map((it) => (
              <option key={it.key} value={it.key}>
                {it.label}
              </option>
            ))}
          </Select>
          <Button
            size="sm"
            variant="outline"
            disabled={!picked || createLink.isPending}
            onClick={() => {
              if (!picked) return;
              // 클릭 시점의 편집기 선택 — 다른 회차/빈 선택이면 거절한다
              const st = useEditorStore.getState();
              const view = st.view;
              if (!view || st.chapterId !== chapterId || projectId === null) {
                toast("에디터에서 연결할 본문을 먼저 선택하세요.", "warning");
                return;
              }
              const { from, to } = view.state.selection.main;
              const excerpt = to > from ? view.state.sliceDoc(from, to) : "";
              if (!excerpt.trim()) {
                toast("에디터에서 연결할 본문을 먼저 선택하세요.", "warning");
                return;
              }
              if (excerpt.length > 500) {
                toast("발췌는 500자 이하로 선택하세요.", "warning");
                return;
              }
              // 미저장 편집분이 서버 content_md에 반영되도록 먼저 flush한다
              void (async () => {
                try {
                  await flushManuscriptDraft(projectId, chapterId);
                } catch (e) {
                  toast((e as Error).message, "error");
                  return;
                }
                createLink.mutate({
                  goal_field: picked.field,
                  item_index: picked.item_index,
                  excerpt,
                });
              })();
            }}
          >
            선택 본문 연결
          </Button>
        </div>
      )}
      {links.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">연결된 근거가 없습니다.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {links.map((link) => (
            <li
              key={link.id}
              className="flex items-center gap-1.5 rounded-sm border border-border bg-background px-1.5 py-1 text-[11px]"
            >
              <span className="min-w-0 flex-1 truncate" title={link.excerpt}>
                {link.goal_item_text} → {link.excerpt}
              </span>
              {link.manuscript_status === "broken" && (
                <Badge variant="revising" className="text-[10px]">
                  원문 파손
                </Badge>
              )}
              {link.goal_status === "drifted" && (
                <Badge variant="secondary" className="text-[10px]">
                  목표 변경됨
                </Badge>
              )}
              {link.goal_status === "goal_deleted" && (
                <Badge variant="outline" className="text-[10px]">
                  목표 삭제됨
                </Badge>
              )}
              <Button
                size="sm"
                variant="ghost"
                className="h-5 px-1 text-[10px] text-destructive"
                aria-label={`근거 링크 삭제: ${link.goal_item_text}`}
                onClick={() => deleteLink.mutate(link.id)}
                disabled={deleteLink.isPending}
              >
                삭제
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** D01 이력 dialog — 버전 목록 + 명시적 복원(새 버전 기록). */
function GoalHistoryDialog({
  open,
  onOpenChange,
  chapterId,
  currentVersion,
  restoring,
  onRestore,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  chapterId: number;
  currentVersion: number | null;
  restoring: boolean;
  onRestore: (goalVersion: number) => void;
}) {
  const historyQuery = useQuery({
    queryKey: ["chapter-goal-history", chapterId],
    queryFn: () =>
      api.get<ChapterGoalRevision[]>(`/chapters/${chapterId}/goal/history`),
    enabled: open,
  });
  const rows = historyQuery.data ?? [];
  return (
    <Dialog open={open} onOpenChange={onOpenChange} aria-label="회차 목표 이력">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>회차 목표 이력</DialogTitle>
          <DialogDescription>
            복원은 과거를 덮지 않고 새 버전으로 기록됩니다.
          </DialogDescription>
        </DialogHeader>
        {historyQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">이력을 불러오는 중…</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">목표 이력이 없습니다.</p>
        ) : (
          <ul className="flex max-h-64 flex-col gap-1.5 overflow-y-auto">
            {rows.map((row) => (
              <li
                key={row.id}
                className="flex items-center justify-between gap-2 rounded-sm border border-border px-2 py-1.5 text-xs"
              >
                <span className="flex min-w-0 flex-col">
                  <span className="font-medium">
                    v{row.goal_version}
                    {row.goal_version === currentVersion ? " · 현재" : ""}
                    {row.restored_from !== null
                      ? ` · v${row.restored_from}에서 복원됨`
                      : ""}
                  </span>
                  <span className="truncate text-muted-foreground">
                    {row.goal.emotion_goal || "(감정 목표 없음)"} · 기준 r
                    {row.base_manuscript_revision ?? "-"} ·{" "}
                    {row.created_at.slice(0, 19).replace("T", " ")}
                  </span>
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={restoring || row.goal_version === currentVersion}
                  onClick={() => onRestore(row.goal_version)}
                >
                  이 버전으로 복원
                </Button>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** 주입 투명성 배지 — 자동으로 곁들여진 컨텍스트를 항상 공개한다 */
function InjectedBadges({ ctx }: { ctx: AiPanelStoreApi["contextSelection"] }) {
  const injectedLore = useAiPanelStore((s) => s.injectedLore);
  const injectedForeshadows = useAiPanelStore((s) => s.injectedForeshadows);
  const injectedOutline = useAiPanelStore((s) => s.injectedOutline);
  const chips: string[] = [];
  if (ctx.sceneId) chips.push("선택 장면");
  if (injectedOutline?.current) chips.push("이번 화 목표");
  if (injectedOutline?.next_title)
    chips.push(`다음 화: ${injectedOutline.next_title}`);
  for (const l of injectedLore) chips.push(`세계관: ${l.title}`);
  for (const f of injectedForeshadows) chips.push(`복선: ${f.title}`);
  if (chips.length === 0) return null;
  return (
    <div
      className="mt-1 flex flex-wrap gap-1"
      aria-label="자동 주입된 컨텍스트"
    >
      {chips.map((c, i) => (
        <Badge key={`${c}-${i}`} variant="secondary" className="text-[10px]">
          {c}
        </Badge>
      ))}
    </div>
  );
}

/** 응답 영역(초안/감수 의견/수정본 탭) + [끼워넣기][선택 교체][복사] — FR-406의 유일한 반영 경로 */
type ResultTab = AiPanelState["resultTab"];

function ResultSection() {
  const status = useAiPanelStore((s) => s.status);
  const streamingText = useAiPanelStore((s) => s.streamingText);
  const reviewText = useAiPanelStore((s) => s.reviewText);
  const refinedText = useAiPanelStore((s) => s.refinedText);
  const resultTab = useAiPanelStore((s) => s.resultTab);
  const setResultTab = useAiPanelStore((s) => s.setResultTab);
  const reviewInfo = useAiPanelStore((s) => s.reviewInfo);
  const resultOrigin = useAiPanelStore((s) => s.resultOrigin);
  const generationOutputIds = useAiPanelStore((s) => s.generationOutputIds);
  const scrollRef = useRef<HTMLDivElement>(null);

  const hasReview =
    reviewText.length > 0 || refinedText.length > 0 || reviewInfo !== null;
  const activeText =
    resultTab === "draft"
      ? streamingText
      : resultTab === "review"
        ? reviewText
        : refinedText;

  // 자동 스크롤(sticky bottom)
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [streamingText, reviewText, refinedText, resultTab]);

  /** E2 — 작가 처분 기록. 실패해도 편집을 막지 않는다(best-effort). */
  const recordOutcome = useCallback(
    (outcome: "inserted" | "replaced" | "copied" | "discarded") => {
      const channel =
        resultTab === "refined"
          ? "refined"
          : resultTab === "review"
            ? "review"
            : "draft";
      const outputId = generationOutputIds[channel];
      if (outputId == null) return;
      const chapterId = resultOrigin?.chapterId ?? null;
      const text = activeText;
      void (async () => {
        let chapterRevision: number | null = null;
        if (chapterId != null) {
          try {
            const ch = await api.get<ChapterDetail>(`/chapters/${chapterId}`);
            chapterRevision = ch.revision;
          } catch {
            /* 처분 앵커 조회 실패는 기록을 막지 않는다 */
          }
        }
        try {
          await api.post(`/generation-outputs/${outputId}/outcome`, {
            outcome,
            landed_text:
              outcome === "copied" || outcome === "discarded"
                ? undefined
                : text,
            chapter_revision: chapterRevision,
          });
        } catch {
          /* 이력 기록 실패는 사용자 액션을 막지 않는다 */
        }
      })();
    },
    [resultTab, generationOutputIds, resultOrigin, activeText],
  );

  /** 끼워넣기 — 현재 회차 본문 끝 append (P1 명시 클릭) */
  const insertAtEnd = useCallback(() => {
    if (!resultMatchesCurrentEditor(useAiPanelStore.getState().resultOrigin)) {
      toast(
        "AI 결과가 다른 회차에서 생성되어 현재 원고에 자동 삽입하지 않았습니다. 복사 후 직접 확인하세요.",
        "warning",
      );
      return;
    }
    const view = useEditorStore.getState().view;
    if (!view) {
      toast("현재 회차 에디터가 없습니다.", "warning");
      return;
    }
    const text = activeText;
    view.dispatch({
      changes: { from: view.state.doc.length, insert: "\n\n" + text },
    });
    view.focus();
    recordOutcome("inserted");
    toast("본문 끝에 끼워넣었습니다.", "success");
  }, [activeText, recordOutcome]);

  /** 선택 교체 — 에디터 선택 범위만 교체, 선택 없으면 끝에 추가 */
  const replaceSelection = useCallback(() => {
    if (!resultMatchesCurrentEditor(useAiPanelStore.getState().resultOrigin)) {
      toast(
        "AI 결과가 다른 회차에서 생성되어 현재 원고에 자동 삽입하지 않았습니다. 복사 후 직접 확인하세요.",
        "warning",
      );
      return;
    }
    const view = useEditorStore.getState().view;
    if (!view) {
      toast("현재 회차 에디터가 없습니다.", "warning");
      return;
    }
    const text = activeText;
    const sel = view.state.selection.main;
    const changes = sel.empty
      ? { from: view.state.doc.length, insert: "\n\n" + text }
      : { from: sel.from, to: sel.to, insert: text };
    view.dispatch({ changes });
    view.focus();
    recordOutcome(sel.empty ? "inserted" : "replaced");
    toast(
      sel.empty
        ? "선택 범위가 없어 본문 끝에 추가했습니다."
        : "선택 범위를 교체했습니다.",
      "success",
    );
  }, [activeText, recordOutcome]);

  const copyResult = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(activeText);
      recordOutcome("copied");
      toast("클립보드에 복사했습니다.", "success");
    } catch {
      toast("클립보드 접근이 거부되었습니다.", "error");
    }
  }, [activeText, recordOutcome]);

  /** E7 — 명시 폐기: 결과를 버리고 discarded 처분을 기록한다(복사≠수용과
   *  같은 이유로 UI 리셋은 폐기가 아니며, 이 버튼만이 폐기 신호다). */
  const discardResult = useCallback(() => {
    recordOutcome("discarded");
    useAiPanelStore.getState().resetResult();
    toast("결과를 폐기했습니다 — 본문에 반영되지 않았습니다.", "info");
  }, [recordOutcome]);

  const busy = status === "streaming";
  const hasText = activeText.length > 0;
  // 감수 의견 탭은 본문 반영 대상이 아니다 — 복사만 허용
  const readOnlyTab = resultTab === "review";
  const canInsertHere = resultMatchesCurrentEditor(resultOrigin);

  const tabs: Array<{ key: ResultTab; label: string; count: number }> = [
    { key: "draft", label: "초안", count: streamingText.length },
    { key: "review", label: "감수 의견", count: reviewText.length },
    { key: "refined", label: "수정본", count: refinedText.length },
  ];

  return (
    <section className="flex min-h-0 flex-col rounded-md border border-border">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <h3 className="text-xs font-semibold text-muted-foreground">
          응답 {busy ? "(스트리밍)" : ""}
        </h3>
        {reviewInfo && (
          <span
            className="text-[10px] text-muted-foreground"
            title="감수 패스 모델"
          >
            감수: {reviewInfo.provider} · {reviewInfo.model}
          </span>
        )}
      </div>
      {hasReview && (
        <div
          className="flex gap-1 border-b border-border px-2 py-1.5"
          role="tablist"
          aria-label="응답 탭"
        >
          {tabs.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={resultTab === t.key}
              disabled={t.count === 0 && t.key !== "draft"}
              onClick={() => setResultTab(t.key)}
              className={
                "rounded-sm px-2 py-1 text-xs transition-colors " +
                (resultTab === t.key
                  ? "bg-muted font-semibold text-foreground"
                  : "text-muted-foreground hover:text-foreground disabled:opacity-40")
              }
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
      <div
        ref={scrollRef}
        className="thin-scroll max-h-64 min-h-24 overflow-y-auto p-3"
      >
        {hasText ? (
          <pre className="whitespace-pre-wrap break-words font-serif text-sm leading-relaxed">
            {activeText}
          </pre>
        ) : (
          <p className="text-sm text-muted-foreground">아직 응답이 없습니다.</p>
        )}
      </div>
      <div
        className="grid grid-cols-4 gap-1.5 border-t border-border p-2"
        title="결과 도착 후 활성화됩니다 (P1)"
      >
        <Button
          size="sm"
          variant="outline"
          disabled={!hasText || busy || readOnlyTab || !canInsertHere}
          onClick={insertAtEnd}
        >
          ↪ 끼워넣기
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!hasText || busy || readOnlyTab || !canInsertHere}
          onClick={replaceSelection}
        >
          ⤳ 선택 교체
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={!hasText || busy}
          onClick={() => void copyResult()}
        >
          ⧉ 복사
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={!hasText || busy}
          onClick={discardResult}
          title="결과를 버리고 '폐기' 처분을 기록합니다"
        >
          ✕ 폐기
        </Button>
      </div>
    </section>
  );
}

// ---------- E7 — 작가 규칙 패널 + 회차 생성 이력 ----------

const RULE_CATEGORY_LABELS: Record<string, string> = {
  style: "문체",
  deleted_expression: "삭제 표현",
  character_voice: "인물 말투",
  pacing: "전개 속도",
  length: "분량",
  recurring_error: "반복 오류",
  canon_gap: "설정 누락",
  long_arc: "장기 흐름",
};

const RULE_STATUS_LABELS: Record<string, string> = {
  proposed: "제안",
  approved: "승인됨",
  rejected: "거절됨",
  retired: "폐기됨",
};

interface ImprovementRuleItem {
  id: number;
  category: string;
  rule_text: string;
  status: string;
  source: string;
  rationale: string | null;
  evidence_json: Array<{
    kind: string;
    id?: number | null;
    text?: string | null;
  }>;
  created_at: string;
}

function RuleRow({
  rule,
  onDecide,
  deciding,
}: {
  rule: ImprovementRuleItem;
  onDecide: (id: number, decision: "approve" | "reject" | "retire") => void;
  deciding: boolean;
}) {
  return (
    <li className="rounded-sm bg-muted px-2 py-2">
      <div className="flex items-center gap-1.5">
        <Badge variant="outline">
          {RULE_CATEGORY_LABELS[rule.category] ?? rule.category}
        </Badge>
        <Badge variant={rule.status === "approved" ? "done" : "outline"}>
          {RULE_STATUS_LABELS[rule.status] ?? rule.status}
        </Badge>
        {rule.source === "system_proposal" && (
          <Badge variant="revising">시스템 제안</Badge>
        )}
      </div>
      <p className="mt-1 text-xs leading-snug">{rule.rule_text}</p>
      {rule.rationale ? (
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          근거: {rule.rationale}
        </p>
      ) : null}
      {rule.evidence_json.length > 0 && (
        <p className="mt-0.5 text-[10px] text-muted-foreground">
          근거 링크{" "}
          {rule.evidence_json
            .map((e) =>
              e.kind === "note"
                ? `메모 “${e.text}”`
                : e.kind === "generation_output"
                  ? `산출물 #${e.id}`
                  : `회차 #${e.id}`,
            )
            .join(" · ")}
        </p>
      )}
      <div className="mt-1.5 flex gap-1.5">
        {rule.status === "proposed" && (
          <>
            <Button
              size="sm"
              variant="outline"
              disabled={deciding}
              onClick={() => onDecide(rule.id, "approve")}
            >
              승인
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={deciding}
              onClick={() => onDecide(rule.id, "reject")}
            >
              거절
            </Button>
          </>
        )}
        {rule.status === "approved" && (
          <Button
            size="sm"
            variant="ghost"
            disabled={deciding}
            onClick={() => onDecide(rule.id, "retire")}
          >
            폐기
          </Button>
        )}
      </div>
    </li>
  );
}

function RulesSection({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const rulesQuery = useQuery({
    queryKey: ["improvement-rules", projectId],
    queryFn: () =>
      api.get<ImprovementRuleItem[]>(
        `/projects/${projectId}/improvement-rules`,
      ),
  });
  const [category, setCategory] = useState("style");
  const [text, setText] = useState("");
  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: ["improvement-rules", projectId],
    });

  const decide = useMutation({
    mutationFn: ({
      id,
      decision,
    }: {
      id: number;
      decision: "approve" | "reject" | "retire";
    }) =>
      api.post(`/projects/${projectId}/improvement-rules/${id}/decision`, {
        decision,
      }),
    onSuccess: () => void invalidate(),
    onError: (e) => toast((e as Error).message, "error"),
  });
  const create = useMutation({
    mutationFn: (status_: "proposed" | "approved") =>
      api.post(`/projects/${projectId}/improvement-rules`, {
        category,
        rule_text: text,
        status: status_,
      }),
    onSuccess: () => {
      setText("");
      void invalidate();
    },
    onError: (e) => toast((e as Error).message, "error"),
  });
  const propose = useMutation({
    mutationFn: () =>
      api.post<{ created_count: number; skipped_existing: number; signals_evaluated: number }>(
        `/projects/${projectId}/improvement-rules/propose`,
        {},
      ),
    onSuccess: (result) => {
      void invalidate();
      toast(
        result.created_count > 0
          ? `생성 이력 분석으로 규칙 제안 ${result.created_count}건을 만들었습니다.`
          : "분석 신호가 임계에 못 미쳐 새 제안이 없습니다.",
        "success",
      );
    },
    onError: (e) => toast((e as Error).message, "error"),
  });

  const rules = rulesQuery.data ?? [];
  const proposed = rules.filter((r) => r.status === "proposed");
  const approved = rules.filter((r) => r.status === "approved");
  const closed = rules.filter(
    (r) => r.status === "rejected" || r.status === "retired",
  );

  return (
    <section className="rounded-md border border-border p-3">
      <div className="mb-1 flex items-center gap-2">
        <h3 className="text-xs font-semibold text-muted-foreground">
          작가 규칙
        </h3>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto h-6 px-2 text-[11px]"
          disabled={propose.isPending}
          onClick={() => propose.mutate()}
          title="초안↔반영본 비교·수용률 분석으로 규칙 제안을 생성합니다"
        >
          {propose.isPending ? "분석 중…" : "이력 분석으로 제안 생성"}
        </Button>
      </div>
      <p className="mb-2 text-[11px] leading-snug text-muted-foreground">
        승인된 규칙만 다음 생성의 [작가 승인 규칙] 블록에 주입됩니다. 제안·거절된
        규칙과 다른 작품의 규칙은 적용되지 않습니다.
      </p>

      {proposed.length > 0 && (
        <>
          <p className="mb-1 text-[11px] font-medium">검토 대기</p>
          <ul className="mb-2 flex flex-col gap-1.5">
            {proposed.map((r) => (
              <RuleRow
                key={r.id}
                rule={r}
                deciding={decide.isPending}
                onDecide={(id, d) => decide.mutate({ id, decision: d })}
              />
            ))}
          </ul>
        </>
      )}
      {approved.length > 0 && (
        <>
          <p className="mb-1 text-[11px] font-medium">적용 중 (승인됨)</p>
          <ul className="mb-2 flex flex-col gap-1.5">
            {approved.map((r) => (
              <RuleRow
                key={r.id}
                rule={r}
                deciding={decide.isPending}
                onDecide={(id, d) => decide.mutate({ id, decision: d })}
              />
            ))}
          </ul>
        </>
      )}
      {closed.length > 0 && (
        <details className="mb-2">
          <summary className="cursor-pointer text-[11px] text-muted-foreground">
            종결된 규칙 {closed.length}개
          </summary>
          <ul className="mt-1 flex flex-col gap-1.5">
            {closed.map((r) => (
              <RuleRow
                key={r.id}
                rule={r}
                deciding={decide.isPending}
                onDecide={(id, d) => decide.mutate({ id, decision: d })}
              />
            ))}
          </ul>
        </details>
      )}
      {rules.length === 0 && !rulesQuery.isPending && (
        <p className="mb-2 text-[11px] text-muted-foreground">
          아직 규칙이 없습니다.
        </p>
      )}

      <div className="flex flex-col gap-1.5 border-t border-border pt-2">
        <div className="flex items-center gap-2">
          <Label htmlFor="rule-category">분류</Label>
          <Select
            id="rule-category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {Object.entries(RULE_CATEGORY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="예: 한 문장은 60자를 넘기지 않는다 / '그러나'로 시작하는 문장을 줄인다"
          rows={2}
          aria-label="새 작가 규칙"
        />
        <div className="flex gap-1.5">
          <Button
            size="sm"
            variant="outline"
            disabled={!text.trim() || create.isPending}
            onClick={() => create.mutate("proposed")}
          >
            제안으로 추가
          </Button>
          <Button
            size="sm"
            disabled={!text.trim() || create.isPending}
            onClick={() => create.mutate("approved")}
            title="직접 쓴 규칙은 즉시 승인 상태로 등록할 수 있습니다"
          >
            승인 규칙으로 추가
          </Button>
        </div>
      </div>
    </section>
  );
}

const SURFACE_LABELS: Record<string, string> = {
  generate: "단일 생성",
  generate_parallel: "병렬 집필",
  review: "감수",
  plan: "계획",
  assistant_generate: "원클릭",
};

const OUTCOME_LABELS: Record<string, string> = {
  pending: "대기",
  inserted: "삽입",
  replaced: "교체",
  copied: "복사",
  discarded: "폐기",
};

interface GenerationRunSummary {
  id: number;
  surface: string;
  status: string;
  model: string | null;
  wall_ms: number;
  created_at: string;
  outputs: Array<{
    id: number;
    channel: string;
    outcome: string;
    output_chars: number;
  }>;
}

function GenerationHistorySection({ chapterId }: { chapterId: number }) {
  const runsQuery = useQuery({
    queryKey: ["generation-runs", chapterId],
    queryFn: () =>
      api.get<GenerationRunSummary[]>(
        `/chapters/${chapterId}/generation-runs`,
      ),
  });
  const runs = runsQuery.data ?? [];
  return (
    <section className="rounded-md border border-border p-3">
      <h3 className="mb-1 text-xs font-semibold text-muted-foreground">
        생성 이력
      </h3>
      <p className="mb-2 text-[11px] leading-snug text-muted-foreground">
        이 회차의 AI 생성·처분 기록입니다. 원고 정본이 아닌 참조 데이터입니다.
      </p>
      {runs.length === 0 && !runsQuery.isPending ? (
        <p className="text-[11px] text-muted-foreground">이력이 없습니다.</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {runs.map((run) => (
            <li key={run.id} className="rounded-sm bg-muted px-2 py-1.5">
              <div className="flex items-center gap-1.5 text-[11px]">
                <span className="font-medium">
                  {SURFACE_LABELS[run.surface] ?? run.surface}
                </span>
                <Badge
                  variant={run.status === "completed" ? "done" : "revising"}
                >
                  {run.status === "completed"
                    ? "완료"
                    : run.status === "aborted"
                      ? "중단"
                      : "오류"}
                </Badge>
                <span className="text-muted-foreground">
                  {(run.wall_ms / 1000).toFixed(0)}초 ·{" "}
                  {new Date(run.created_at).toLocaleString("ko-KR")}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {run.outputs.map((o) => (
                  <Badge key={o.id} variant="outline" className="text-[10px]">
                    {o.channel}
                    {o.outcome !== "pending" &&
                      ` → ${OUTCOME_LABELS[o.outcome] ?? o.outcome}`}
                  </Badge>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ShieldCheckSlot() {
  return (
    <ShieldCheckIcon className="mr-1 inline-block align-text-bottom text-info" />
  );
}
function CloudUploadSlot() {
  return (
    <CloudUploadIcon className="mr-1 inline-block align-text-bottom text-warning" />
  );
}
