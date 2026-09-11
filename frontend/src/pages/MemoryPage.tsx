import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type Chapter,
  type MemoryEntry,
  type MemoryEntryCreate,
  type MemoryKind,
  type MemoryVisibility,
  type Project,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";

const KINDS: Array<{ value: MemoryKind; label: string }> = [
  { value: "summary", label: "요약" },
  { value: "beat", label: "비트" },
  { value: "decision", label: "결정" },
  { value: "fact", label: "사실" },
  { value: "timeline", label: "시간축" },
  { value: "relationship_note", label: "관계 메모" },
];

const VISIBILITIES: Array<{ value: MemoryVisibility; label: string }> = [
  { value: "draft", label: "초안" },
  { value: "approved", label: "승인" },
  { value: "retired", label: "폐기" },
];

function optionalNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function memoryLabel(kind: MemoryKind): string {
  return KINDS.find((item) => item.value === kind)?.label ?? kind;
}

function visibilityClass(visibility: MemoryVisibility): string {
  if (visibility === "approved") return "text-success";
  if (visibility === "retired") return "text-muted-foreground";
  return "text-warning";
}

function provenanceLabel(provenance: Record<string, unknown>): string {
  const pairs = Object.entries(provenance)
    .filter(([, value]) =>
      ["string", "number", "boolean"].includes(typeof value),
    )
    .map(([key, value]) => `${key}: ${String(value)}`);
  return pairs.join(" · ") || "수동 입력";
}

function buildListPath(
  pid: number,
  filters: {
    kind: MemoryKind | "";
    visibility: MemoryVisibility | "";
    stale: "" | "true" | "false";
    chapterId: string;
  },
): string {
  const params = new URLSearchParams();
  if (filters.kind) params.set("kind", filters.kind);
  if (filters.visibility) params.set("visibility", filters.visibility);
  if (filters.stale) params.set("stale", filters.stale);
  if (filters.chapterId) params.set("chapter_id", filters.chapterId);
  const query = params.toString();
  return `/projects/${pid}/memories${query ? `?${query}` : ""}`;
}

export function MemoryPage() {
  const { pid: rawPid } = useParams();
  const pid = Number(rawPid);
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<MemoryKind | "">("");
  const [visibility, setVisibility] = useState<MemoryVisibility | "">("");
  const [stale, setStale] = useState<"" | "true" | "false">("");
  const [chapterId, setChapterId] = useState("");
  const [memoryKind, setMemoryKind] = useState<MemoryKind>("fact");
  const [body, setBody] = useState("");
  const [sourceChapter, setSourceChapter] = useState("");
  const [fromSortOrder, setFromSortOrder] = useState("");
  const [toSortOrder, setToSortOrder] = useState("");
  const [confirming, setConfirming] = useState<number | null>(null);
  const confirmationRef = useRef<HTMLButtonElement>(null);

  const projectQuery = useQuery({
    queryKey: ["project", pid],
    queryFn: () => api.get<Project>(`/projects/${pid}`),
  });
  const chaptersQuery = useQuery({
    queryKey: ["chapters", pid],
    queryFn: () => api.get<Chapter[]>(`/projects/${pid}/chapters`),
  });
  const memoriesQuery = useQuery({
    queryKey: ["memories", pid, kind, visibility, stale, chapterId],
    queryFn: () =>
      api.get<MemoryEntry[]>(
        buildListPath(pid, { kind, visibility, stale, chapterId }),
      ),
  });
  const create = useMutation({
    mutationFn: (payload: MemoryEntryCreate) =>
      api.post<MemoryEntry>(`/projects/${pid}/memories`, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memories", pid] });
      setBody("");
      setSourceChapter("");
      setFromSortOrder("");
      setToSortOrder("");
      toast("장편 기억 초안을 추가했습니다.", "success");
    },
    onError: (error) =>
      toast(`기억 추가 실패: ${(error as Error).message}`, "error"),
  });
  const update = useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: number;
      patch: { visibility: MemoryVisibility };
    }) => api.patch<MemoryEntry>(`/projects/${pid}/memories/${id}`, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memories", pid] });
      setConfirming(null);
      toast("장편 기억 상태를 변경했습니다.", "success");
    },
    onError: (error) =>
      toast(`기억 상태 변경 실패: ${(error as Error).message}`, "error"),
  });

  const chapters = chaptersQuery.data ?? [];
  const chapterTitleById = useMemo(
    () =>
      new Map(
        chapters.map((chapter) => [
          chapter.id,
          chapter.title.trim() || `${chapter.id}화`,
        ]),
      ),
    [chapters],
  );
  const memories = memoriesQuery.data ?? [];

  useEffect(() => {
    if (confirming !== null) confirmationRef.current?.focus();
  }, [confirming]);

  const submit = () => {
    const trimmedBody = body.trim();
    const from = optionalNumber(fromSortOrder);
    const to = optionalNumber(toSortOrder);
    if (!trimmedBody) return;
    if (
      (fromSortOrder.trim() && from === null) ||
      (toSortOrder.trim() && to === null)
    ) {
      toast("적용 범위는 숫자로 입력하세요.", "error");
      return;
    }
    if (from !== null && to !== null && from > to) {
      toast("적용 시작 값은 종료 값보다 클 수 없습니다.", "error");
      return;
    }
    create.mutate({
      kind: memoryKind,
      body: trimmedBody,
      chapter_id: sourceChapter ? Number(sourceChapter) : null,
      effective_from_sort_order: from,
      effective_to_sort_order: to,
    });
  };

  return (
    <div className="mx-auto flex h-full max-w-[920px] flex-col gap-4 overflow-y-auto px-6 py-4">
      <header className="flex flex-wrap items-start gap-2">
        <div>
          <h1 className="text-lg font-semibold">장편 기억</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            작품: {projectQuery.data?.title ?? "불러오는 중…"}
          </p>
          {projectQuery.data?.synopsis && (
            <p className="mt-1 max-w-[680px] truncate text-xs text-muted-foreground">
              {projectQuery.data.synopsis}
            </p>
          )}
          <p className="mt-1 text-xs text-muted-foreground">
            원고를 바꾸지 않고, 작가가 직접 검토한 provenance 기억만 AI 집필에
            참고시킵니다.
          </p>
        </div>
        <Badge variant="secondary" className="ml-auto">
          {memories.length}건
        </Badge>
      </header>

      <section
        className="rounded-md border border-border p-3"
        aria-labelledby="memory-create-title"
      >
        <h2 id="memory-create-title" className="mb-3 text-sm font-semibold">
          기억 초안 추가
        </h2>
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <Label htmlFor="memory-kind">종류</Label>
            <Select
              id="memory-kind"
              value={memoryKind}
              onChange={(event) =>
                setMemoryKind(event.target.value as MemoryKind)
              }
            >
              {KINDS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="memory-source-chapter">근거 회차(선택)</Label>
            <Select
              id="memory-source-chapter"
              value={sourceChapter}
              onChange={(event) => setSourceChapter(event.target.value)}
            >
              <option value="">작품 전체 메모</option>
              {chapters.map((chapter) => (
                <option key={chapter.id} value={chapter.id}>
                  {chapterTitleById.get(chapter.id)}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <Label htmlFor="memory-body" className="mt-3 block">
          내용
        </Label>
        <Textarea
          id="memory-body"
          rows={3}
          maxLength={20_000}
          placeholder="작가가 직접 확인할 사실·결정·요약을 입력하세요."
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />
        <div className="mt-3 grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
          <div>
            <Label htmlFor="memory-from">적용 시작 sort order</Label>
            <Input
              id="memory-from"
              inputMode="decimal"
              value={fromSortOrder}
              onChange={(event) => setFromSortOrder(event.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="memory-to">적용 종료 sort order</Label>
            <Input
              id="memory-to"
              inputMode="decimal"
              value={toSortOrder}
              onChange={(event) => setToSortOrder(event.target.value)}
            />
          </div>
          <Button disabled={create.isPending || !body.trim()} onClick={submit}>
            {create.isPending ? "추가 중…" : "초안 추가"}
          </Button>
        </div>
        <p
          className="mt-2 text-[11px] text-muted-foreground"
          aria-live="polite"
        >
          저장 시 근거 회차의 현재 revision/hash는 서버가 계산하며, 새 기억은
          항상 초안으로 시작합니다.
        </p>
      </section>

      <section className="flex flex-wrap gap-2" aria-label="장편 기억 필터">
        <Select
          aria-label="기억 종류 필터"
          className="w-40"
          value={kind}
          onChange={(event) => setKind(event.target.value as MemoryKind | "")}
        >
          <option value="">모든 종류</option>
          {KINDS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </Select>
        <Select
          aria-label="기억 상태 필터"
          className="w-32"
          value={visibility}
          onChange={(event) =>
            setVisibility(event.target.value as MemoryVisibility | "")
          }
        >
          <option value="">모든 상태</option>
          {VISIBILITIES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </Select>
        <Select
          aria-label="stale 필터"
          className="w-36"
          value={stale}
          onChange={(event) =>
            setStale(event.target.value as "" | "true" | "false")
          }
        >
          <option value="">stale 전체</option>
          <option value="false">현재 원문과 일치</option>
          <option value="true">stale만</option>
        </Select>
        <Select
          aria-label="근거 회차 필터"
          className="w-44"
          value={chapterId}
          onChange={(event) => setChapterId(event.target.value)}
        >
          <option value="">모든 근거 회차</option>
          {chapters.map((chapter) => (
            <option key={chapter.id} value={chapter.id}>
              {chapterTitleById.get(chapter.id)}
            </option>
          ))}
        </Select>
      </section>

      {memoriesQuery.isPending && (
        <p className="text-sm text-muted-foreground">기억을 불러오는 중…</p>
      )}
      {memoriesQuery.isError && (
        <p role="alert" className="text-sm text-destructive">
          기억 목록을 불러오지 못했습니다. 잠시 후 다시 시도하세요.
        </p>
      )}
      {!memoriesQuery.isPending && memories.length === 0 && (
        <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          조건에 맞는 장편 기억이 없습니다.
        </p>
      )}
      <section
        className="flex flex-col gap-2"
        aria-live="polite"
        aria-label="장편 기억 목록"
      >
        {memories.map((memory) => (
          <article
            key={memory.id}
            className="rounded-md border border-border p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{memoryLabel(memory.kind)}</Badge>
              <span
                className={`text-xs font-semibold ${visibilityClass(memory.visibility)}`}
              >
                {
                  VISIBILITIES.find((item) => item.value === memory.visibility)
                    ?.label
                }
              </span>
              {memory.stale && (
                <Badge
                  variant="outline"
                  className="border-destructive/40 text-destructive"
                >
                  stale — 자동 주입 제외
                </Badge>
              )}
              <span className="ml-auto text-[11px] text-muted-foreground">
                #{memory.id}
              </span>
            </div>
            <p className="mt-2 whitespace-pre-wrap text-sm">{memory.body}</p>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
              <span>근거: {memory.source_chapter_title ?? "작품 전체"}</span>
              <span>revision: {memory.source_revision ?? "—"}</span>
              <span>hash: {memory.source_sha256.slice(0, 12)}…</span>
              <span>provenance: {provenanceLabel(memory.provenance)}</span>
              {(memory.effective_from_sort_order !== null ||
                memory.effective_to_sort_order !== null) && (
                <span>
                  범위: {memory.effective_from_sort_order ?? "—"} ~{" "}
                  {memory.effective_to_sort_order ?? "—"}
                </span>
              )}
            </div>
            {memory.stale && (
              <p className="mt-2 text-xs text-warning" role="status">
                원문 revision/hash가 달라져 자동 주입하지 않습니다. 새 원문 기준
                기억은 별도로 추가하세요.
              </p>
            )}
            {memory.visibility !== "retired" && (
              <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
                {confirming === memory.id ? (
                  <div
                    className="flex flex-wrap items-center gap-2"
                    role="group"
                    aria-label="장편 기억 상태 변경 확인"
                  >
                    <span className="text-xs text-muted-foreground">
                      상태를 변경할까요?
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setConfirming(null)}
                    >
                      취소
                    </Button>
                    <Button
                      ref={confirmationRef}
                      size="sm"
                      variant={
                        memory.visibility === "draft"
                          ? "default"
                          : "destructive"
                      }
                      disabled={update.isPending}
                      onClick={() =>
                        update.mutate({
                          id: memory.id,
                          patch: {
                            visibility:
                              memory.visibility === "draft"
                                ? "approved"
                                : "retired",
                          },
                        })
                      }
                    >
                      확인
                    </Button>
                  </div>
                ) : (
                  <>
                    {memory.visibility === "draft" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setConfirming(memory.id)}
                      >
                        승인
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setConfirming(memory.id)}
                    >
                      폐기
                    </Button>
                  </>
                )}
              </div>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
