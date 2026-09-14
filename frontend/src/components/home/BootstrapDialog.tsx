import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type AssistantGenerateNextResponse,
  type AssistantPlanNextResponse,
  type BootstrapRequest,
  type BootstrapResponse,
  type GenerationOutputApplyResult,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * ✨ AI 부트스트랩 마법사 — POST /api/v1/projects/bootstrap.
 * 1단계: 장르·프리미스·권/회차 폼 → 2단계: 생성 진행(단계별 라벨) → 완료: 요약 카드.
 * P3 저장상태 톤 — 진행 중 이탈 방지 문구, 실패 시 재시도 버튼.
 */

const GENRE_PRESETS = [
  "판타지",
  "무협",
  "현대판타지",
  "로맨스",
  "미스터리",
] as const;

/** 단계별 라벨 — 백엔드 LLM 3회 호출(제목→목차→캐릭터·세계관) 순서에 대응 */
const STAGES = ["제목 발상", "목차 설계", "캐릭터·세계관 구축"] as const;
/** 단계당 표시 시간 — 실제 응답이 늦으면 마지막 단계에서 대기 표시 */
const STAGE_MS = 8_000;

export function BootstrapDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [genreChoice, setGenreChoice] = useState<string>(GENRE_PRESETS[0]);
  const [customGenre, setCustomGenre] = useState("");
  const [premise, setPremise] = useState("");
  const [volumeCount, setVolumeCount] = useState(1);
  const [chaptersPerVolume, setChaptersPerVolume] = useState(10);

  /** 생성 중 "멈춤 아님" 피드백 — 0.3s마다 진행 바를 조금씩 올림(상한 95%) */
  const [elapsedPct, setElapsedPct] = useState(0);
  const [stageIdx, setStageIdx] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stageTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const bootstrap = useMutation({
    mutationFn: (body: BootstrapRequest) =>
      api.post<BootstrapResponse>("/projects/bootstrap", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  /** assistant 게이트 — 계획 검토 → 초안 미리보기 → 명시 적용. 원고 자동 덮어쓰기 없음 */
  const [assistantStage, setAssistantStage] = useState<
    "idle" | "plan" | "draft"
  >("idle");

  const planNext = useMutation({
    mutationFn: (projectId: number) =>
      api.post<AssistantPlanNextResponse>(
        `/projects/${projectId}/assistant/plan-next`,
        {},
      ),
    onSuccess: () => setAssistantStage("plan"),
  });

  const generateNext = useMutation({
    mutationFn: (args: {
      projectId: number;
      plan: AssistantPlanNextResponse;
    }) =>
      api.post<AssistantGenerateNextResponse>(
        `/projects/${args.projectId}/assistant/generate-next`,
        {
          chapter_id: args.plan.chapter_id,
          approved_plan: args.plan.plan,
          plan_output_id: args.plan.plan_output_id,
        },
      ),
    onSuccess: () => setAssistantStage("draft"),
  });

  const applyDraft = useMutation({
    mutationFn: (args: { outputId: number; revision: number }) =>
      api.post<GenerationOutputApplyResult>(
        `/generation-outputs/${args.outputId}/apply`,
        { expected_revision: args.revision },
      ),
    onSuccess: (applied) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      // 서버가 저장한 정본을 편집기가 다시 읽도록 회차 앵커와 함께 이동한다.
      const pid = bootstrap.data?.project_id;
      bootstrap.reset();
      onOpenChange(false);
      navigate(
        pid
          ? `/projects/${pid}/write?chapter=${applied.chapter_id}`
          : "/",
      );
    },
  });

  const discardDraft = useMutation({
    mutationFn: (outputId: number) =>
      api.post(`/generation-outputs/${outputId}/outcome`, {
        outcome: "discarded",
      }),
  });

  const isBusy =
    bootstrap.isPending ||
    planNext.isPending ||
    generateNext.isPending ||
    applyDraft.isPending;

  // 생성 중: 진행 바 애니메이션 + 단계 라벨 순환
  useEffect(() => {
    if (!isBusy) return;
    setElapsedPct(4);
    setStageIdx(0);
    timerRef.current = setInterval(() => {
      setElapsedPct((p) => Math.min(p + 1, 95));
    }, 300);
    stageTimerRef.current = setInterval(() => {
      setStageIdx((i) => Math.min(i + 1, STAGES.length - 1));
    }, STAGE_MS);
    return () => {
      for (const ref of [timerRef, stageTimerRef]) {
        if (ref.current) clearInterval(ref.current);
        ref.current = null;
      }
    };
  }, [isBusy]);

  const reset = () => {
    setGenreChoice(GENRE_PRESETS[0]);
    setCustomGenre("");
    setPremise("");
    setVolumeCount(1);
    setChaptersPerVolume(10);
    bootstrap.reset();
    planNext.reset();
    generateNext.reset();
    applyDraft.reset();
    discardDraft.reset();
    setAssistantStage("idle");
  };

  /** 생성 중에는 닫기/Esc 무시 — 이탈 방지(P3 저장상태 톤) */
  const handleClose = (next: boolean) => {
    if (!next && isBusy) return;
    if (!next) reset();
    onOpenChange(next);
  };

  const effectiveGenre =
    genreChoice === "__custom__" ? customGenre.trim() : genreChoice;

  const start = () => {
    bootstrap.mutate({
      genre: effectiveGenre,
      premise: premise.trim() || null,
      volume_count: volumeCount,
      chapters_per_volume: chaptersPerVolume,
    });
  };

  const result = bootstrap.data;
  const step: "form" | "running" | "done" =
    result != null ? "done" : isBusy ? "running" : "form";

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg">
        {step === "form" && (
          <>
            <DialogHeader>
              <DialogTitle>✨ AI로 작품 자동 생성</DialogTitle>
              <DialogDescription>
                장르와 프리미스만 넣으면 제목·목차·캐릭터·세계관을 한 번에
                만들어 드립니다.
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label>장르 *</Label>
                <div className="flex flex-wrap gap-2">
                  {GENRE_PRESETS.map((g) => (
                    <button
                      key={g}
                      type="button"
                      className={cn(
                        "rounded-full border px-3 py-1 text-sm transition-colors duration-fast",
                        genreChoice === g
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background hover:bg-muted",
                      )}
                      onClick={() => setGenreChoice(g)}
                    >
                      {g}
                    </button>
                  ))}
                  <button
                    type="button"
                    className={cn(
                      "rounded-full border px-3 py-1 text-sm transition-colors duration-fast",
                      genreChoice === "__custom__"
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-background hover:bg-muted",
                    )}
                    onClick={() => setGenreChoice("__custom__")}
                  >
                    직접입력
                  </button>
                </div>
                {genreChoice === "__custom__" && (
                  <Input
                    autoFocus
                    placeholder="장르 입력 (예: SF 서스펜스)"
                    value={customGenre}
                    onChange={(e) => setCustomGenre(e.target.value)}
                    maxLength={100}
                  />
                )}
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="bootstrap-premise">한 줄 프리미스</Label>
                <Input
                  id="bootstrap-premise"
                  placeholder="비워두면 AI가 발상합니다"
                  value={premise}
                  onChange={(e) => setPremise(e.target.value)}
                  maxLength={2000}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="bootstrap-volume">권 수</Label>
                <Input
                  id="bootstrap-volume"
                  type="number"
                  min={1}
                  max={50}
                  value={volumeCount}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setVolumeCount(
                      Number.isFinite(v)
                        ? Math.min(Math.max(Math.floor(v), 1), 50)
                        : 1,
                    );
                  }}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="bootstrap-chapters">
                  권당 회차 수:{" "}
                  <span className="text-foreground font-semibold">
                    {chaptersPerVolume}
                  </span>
                  회차
                </Label>
                <Slider
                  id="bootstrap-chapters"
                  min={5}
                  max={30}
                  step={1}
                  value={chaptersPerVolume}
                  onChange={(e) =>
                    setChaptersPerVolume(Number(e.currentTarget.value))
                  }
                />
                <div
                  className="flex justify-between text-xs text-muted-foreground"
                  aria-hidden="true"
                >
                  <span>5</span>
                  <span>30</span>
                </div>
              </div>
            </div>

            {bootstrap.isError && (
              <Alert variant="error" className="mt-3">
                <AlertDescription className="flex items-center gap-3">
                  <span className="min-w-0 flex-1">
                    {(bootstrap.error as Error).message ||
                      "생성에 실패했습니다."}
                  </span>
                  <Button size="sm" onClick={start} disabled={!effectiveGenre}>
                    재시도
                  </Button>
                </AlertDescription>
              </Alert>
            )}

            <DialogFooter>
              <Button variant="ghost" onClick={() => handleClose(false)}>
                취소
              </Button>
              <Button disabled={!effectiveGenre} onClick={start}>
                생성 시작
              </Button>
            </DialogFooter>
          </>
        )}

        {step === "running" && (
          <>
            <DialogHeader>
              <DialogTitle>작품 생성 중…</DialogTitle>
              <DialogDescription>
                창을 닫거나 페이지를 벗어나면 생성이 중단될 수 있어요. 잠시만
                기다려 주세요.
              </DialogDescription>
            </DialogHeader>

            <Progress value={elapsedPct} className="my-2" />

            <ol className="flex flex-col gap-2">
              {STAGES.map((label, i) => {
                const state =
                  i < stageIdx ? "done" : i === stageIdx ? "active" : "wait";
                return (
                  <li key={label} className="flex items-center gap-2 text-sm">
                    <span
                      aria-hidden="true"
                      className={cn(
                        "grid size-5 shrink-0 place-items-center rounded-full border text-[10px]",
                        state === "done" &&
                          "border-primary bg-primary text-primary-foreground",
                        state === "active" &&
                          "animate-pulse border-primary text-primary",
                        state === "wait" &&
                          "border-border text-muted-foreground",
                      )}
                    >
                      {state === "done" ? "✓" : i + 1}
                    </span>
                    <span
                      className={cn(
                        state === "active" && "text-foreground font-medium",
                        state === "wait" && "text-muted-foreground",
                        state === "done" && "text-muted-foreground",
                      )}
                    >
                      {label}
                      {state === "active" ? "…" : ""}
                    </span>
                  </li>
                );
              })}
            </ol>

            <p className="mt-3 text-xs text-muted-foreground">
              AI 응답에 몇 분 정도 걸릴 수 있습니다. 완료될 때까지 이 창을 열어
              두세요.
            </p>
          </>
        )}

        {step === "done" && result && (
          <>
            <DialogHeader>
              <DialogTitle>작품 생성 완료 🎉</DialogTitle>
              <DialogDescription>
                {result.fallback
                  ? "GPT OAuth 호출 없이 규칙 기반 템플릿으로 생성되었습니다."
                  : "AI가 만든 구조로 프로젝트가 저장되었습니다."}
              </DialogDescription>
            </DialogHeader>

            <div className="rounded-lg border border-border bg-card p-4">
              <div className="mb-1 flex items-center gap-2">
                <h3 className="truncate text-base font-semibold">
                  {result.title}
                </h3>
                <Badge variant="secondary" className="shrink-0">
                  {result.volume_count}권 · 회차 {result.chapter_count}개
                </Badge>
              </div>
              <p className="mb-3 line-clamp-3 text-sm text-muted-foreground">
                {result.logline}
              </p>
              <dl className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-md bg-muted p-2">
                  <dt className="text-xs text-muted-foreground">회차</dt>
                  <dd className="text-base font-semibold">
                    {result.chapter_count}개
                  </dd>
                </div>
                <div className="rounded-md bg-muted p-2">
                  <dt className="text-xs text-muted-foreground">캐릭터</dt>
                  <dd className="text-base font-semibold">
                    {result.character_count}명
                  </dd>
                </div>
                <div className="rounded-md bg-muted p-2">
                  <dt className="text-xs text-muted-foreground">로어북</dt>
                  <dd className="text-base font-semibold">
                    {result.lore_count}건
                  </dd>
                </div>
              </dl>
              {(result.volume_note_count ?? 0) > 0 && (
                <p className="mt-2 text-[11px] text-muted-foreground">
                  ✓ 권 개요 {result.volume_note_count}권도 함께 생성됐습니다
                  (기획 페이지에서 확인·편집)
                </p>
              )}
            </div>

            {assistantStage === "idle" && (
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-4">
                <p className="text-sm font-medium">
                  AI가 제목·세계관·캐릭터·목차·회차 목표·문체·컨텍스트를
                  준비했습니다.
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  이 설정으로 다음 빈 회차의 집필 계획을 만들어 보여드립니다.
                  계획을 검토한 뒤 집필을 승인하면 초안이 만들어지고, 원고에는
                  작가가 직접 적용할 때만 반영됩니다.
                </p>
              </div>
            )}

            {assistantStage === "plan" && planNext.data && (
              <div className="rounded-lg border border-border bg-card p-3">
                <p className="mb-1 text-xs font-semibold text-muted-foreground">
                  집필 계획 — {planNext.data.chapter_title}
                </p>
                <p className="mb-2 text-[11px] text-muted-foreground">
                  전체 계획을 검토한 뒤 [수락하고 집필]을 누르면 이 계획대로
                  초안을 씁니다. 원고에는 아직 아무것도 반영되지 않았습니다.
                </p>
                <ol className="thin-scroll flex max-h-48 flex-col gap-1.5 overflow-y-auto">
                  {planNext.data.plan.scenes.map((scene) => (
                    <li
                      key={scene.order}
                      className="rounded-sm bg-muted px-2 py-1.5"
                    >
                      <p className="text-xs font-medium">
                        {scene.order}. {scene.title}
                      </p>
                      <p className="mt-0.5 text-[11px] text-muted-foreground">
                        {scene.purpose} · {scene.objective}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        선택: {scene.choice} / 대가: {scene.cost}
                      </p>
                      {(scene.closing_hook || scene.ending_intent) && (
                        <p className="text-[11px] text-muted-foreground">
                          {scene.closing_hook
                            ? `후크: ${scene.closing_hook}`
                            : `결말: ${scene.ending_intent}`}
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {assistantStage === "draft" && generateNext.data && (
              <div className="rounded-lg border border-border bg-card p-3">
                <p className="mb-1 text-xs font-semibold text-muted-foreground">
                  초안 미리보기 — {generateNext.data.chapter_title} ·{" "}
                  {generateNext.data.word_count_cache.toLocaleString()}자
                </p>
                <p className="mb-2 text-[11px] text-warning">
                  아직 원고에 반영되지 않은 초안입니다. [원고에 적용하고 편집]을
                  눌러야 정본이 됩니다.
                </p>
                <pre className="thin-scroll max-h-48 overflow-y-auto whitespace-pre-wrap break-words rounded-sm bg-muted p-2 font-serif text-xs leading-relaxed">
                  {generateNext.data.content_md}
                </pre>
              </div>
            )}

            {(planNext.isError || generateNext.isError || applyDraft.isError) && (
              <Alert variant="error" className="mt-3">
                <AlertDescription>
                  {(planNext.error as Error | null)?.message ||
                    (generateNext.error as Error | null)?.message ||
                    (applyDraft.error as Error | null)?.message ||
                    "다음 회차 생성에 실패했습니다."}
                </AlertDescription>
              </Alert>
            )}

            <DialogFooter>
              {assistantStage === "idle" && (
                <>
                  <Button variant="ghost" onClick={() => handleClose(false)}>
                    닫기
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      handleClose(false);
                      navigate(`/projects/${result.project_id}/write`);
                    }}
                  >
                    프로젝트 열기 →
                  </Button>
                  <Button
                    disabled={isBusy}
                    onClick={() => planNext.mutate(result.project_id)}
                  >
                    {planNext.isPending ? "계획 분석 중…" : "생성 시작"}
                  </Button>
                </>
              )}
              {assistantStage === "plan" && planNext.data && (
                <>
                  <Button
                    variant="ghost"
                    disabled={isBusy}
                    onClick={() => {
                      const pid = result.project_id;
                      handleClose(false);
                      navigate(`/projects/${pid}/write`);
                    }}
                  >
                    나중에
                  </Button>
                  <Button
                    variant="outline"
                    disabled={isBusy}
                    onClick={() => planNext.mutate(result.project_id)}
                  >
                    {planNext.isPending ? "계획 분석 중…" : "계획 다시 생성"}
                  </Button>
                  <Button
                    disabled={isBusy}
                    onClick={() =>
                      generateNext.mutate({
                        projectId: result.project_id,
                        plan: planNext.data!,
                      })
                    }
                  >
                    {generateNext.isPending
                      ? "초안 집필 중…"
                      : "수락하고 집필"}
                  </Button>
                </>
              )}
              {assistantStage === "draft" && generateNext.data && (
                <>
                  <Button
                    variant="ghost"
                    disabled={isBusy}
                    onClick={() => {
                      const draft = generateNext.data;
                      if (draft?.draft_output_id) {
                        discardDraft.mutate(draft.draft_output_id);
                      }
                      handleClose(false);
                      navigate(`/projects/${result.project_id}/write`);
                    }}
                  >
                    폐기
                  </Button>
                  <Button
                    variant="outline"
                    disabled={isBusy}
                    onClick={() => setAssistantStage("plan")}
                  >
                    계획으로
                  </Button>
                  <Button
                    disabled={isBusy || !generateNext.data.draft_output_id}
                    onClick={() =>
                      applyDraft.mutate({
                        outputId: generateNext.data.draft_output_id!,
                        revision: generateNext.data.revision,
                      })
                    }
                  >
                    {applyDraft.isPending
                      ? "적용 중…"
                      : "원고에 적용하고 편집"}
                  </Button>
                </>
              )}
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
