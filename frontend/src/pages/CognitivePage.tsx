import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  api,
  type Chapter,
  type Character,
  type CognitiveVisibility,
  type EventImpact,
  type EventImpactCreate,
  type KnowledgeState,
  type KnowledgeStateCreate,
  type KnowledgeStatus,
  type KnowledgeSubjectType,
  type KnowledgeTargetKind,
  type MemoryEntry,
  type LoreEntry,
} from "@/lib/api";

interface Foreshadow {
  id: number;
  title: string;
}
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";

const SUBJECT_TYPES: Array<{ value: KnowledgeSubjectType; label: string }> = [
  { value: "author", label: "작가" },
  { value: "reader", label: "독자" },
  { value: "character", label: "인물" },
];

const TARGET_KINDS: Array<{ value: KnowledgeTargetKind; label: string }> = [
  { value: "fact", label: "사실" },
  { value: "foreshadow", label: "복선" },
  { value: "lore", label: "로어" },
  { value: "event", label: "사건" },
];

const STATUSES: Array<{ value: KnowledgeStatus; label: string }> = [
  { value: "unaware", label: "모름" },
  { value: "aware", label: "앎" },
  { value: "false_belief", label: "잘못 앎" },
  { value: "forgotten", label: "잊음" },
];

const VISIBILITIES: Array<{ value: CognitiveVisibility; label: string }> = [
  { value: "draft", label: "초안" },
  { value: "approved", label: "승인" },
  { value: "retired", label: "폐기" },
];

function visibilityClass(v: CognitiveVisibility): string {
  if (v === "approved") return "text-success";
  if (v === "retired") return "text-muted-foreground";
  return "text-warning";
}

function statusLabel(s: KnowledgeStatus): string {
  return STATUSES.find((x) => x.value === s)?.label ?? s;
}

function subjectLabel(s: KnowledgeSubjectType): string {
  return SUBJECT_TYPES.find((x) => x.value === s)?.label ?? s;
}

function targetLabel(k: KnowledgeTargetKind): string {
  return TARGET_KINDS.find((x) => x.value === k)?.label ?? k;
}

export default function CognitivePage() {
  const { pid } = useParams<{ pid: string }>();
  const projectId = Number(pid);
  const [tab, setTab] = useState<"knowledge" | "events">("knowledge");

  // ---- knowledge state form ----
  const [kSubject, setKSubject] = useState<KnowledgeSubjectType>("reader");
  const [kCharId, setKCharId] = useState("");
  const [kTargetKind, setKTargetKind] = useState<KnowledgeTargetKind>("fact");
  const [kTargetId, setKTargetId] = useState("");
  const [kStatus, setKStatus] = useState<KnowledgeStatus>("unaware");
  const [kChapterId, setKChapterId] = useState("");
  const [kSortOrder, setKSortOrder] = useState("");

  // ---- event impact form ----
  const [eChapterId, setEChapterId] = useState("");
  const [eLabel, setELabel] = useState("");
  const [eCharDeltas, setECharDeltas] = useState("");
  const [eRelDeltas, setERelDeltas] = useState("");
  const [eFsDeltas, setEFsDeltas] = useState("");
  const [eStateAfter, setEStateAfter] = useState("");

  // ---- filters ----
  const [fSubject, setFSubject] = useState("");
  const [fVisibility, setFVisibility] = useState("");

  // ---- queries ----
  const { data: chapters } = useQuery({
    queryKey: ["chapters", projectId],
    queryFn: () => api.get<Chapter[]>(`/projects/${projectId}/chapters`),
    enabled: Number.isFinite(projectId),
  });
  const { data: characters } = useQuery({
    queryKey: ["characters", projectId],
    queryFn: () => api.get<Character[]>(`/projects/${projectId}/characters`),
    enabled: Number.isFinite(projectId),
  });
  const { data: memories } = useQuery({
    queryKey: ["memories", projectId],
    queryFn: () => api.get<MemoryEntry[]>(`/projects/${projectId}/memories`),
    enabled: Number.isFinite(projectId),
  });
  const { data: foreshadows } = useQuery({
    queryKey: ["foreshadows", projectId],
    queryFn: () => api.get<Foreshadow[]>(`/projects/${projectId}/foreshadows`),
    enabled: Number.isFinite(projectId),
  });
  const { data: loreEntries } = useQuery({
    queryKey: ["lore", projectId],
    queryFn: () => api.get<LoreEntry[]>(`/projects/${projectId}/lore`),
    enabled: Number.isFinite(projectId),
  });
  const { data: knowledgeStates, refetch: refetchKnowledge } = useQuery({
    queryKey: ["knowledge-states", projectId, fSubject, fVisibility],
    queryFn: () => {
      const params = new URLSearchParams();
      if (fSubject) params.set("subject_type", fSubject);
      if (fVisibility) params.set("visibility", fVisibility);
      const qs = params.toString();
      return api.get<KnowledgeState[]>(
        `/projects/${projectId}/knowledge-states${qs ? `?${qs}` : ""}`,
      );
    },
    enabled: Number.isFinite(projectId),
  });
  const { data: eventImpacts, refetch: refetchEvents } = useQuery({
    queryKey: ["event-impacts", projectId],
    queryFn: () =>
      api.get<EventImpact[]>(`/projects/${projectId}/event-impacts`),
    enabled: Number.isFinite(projectId),
  });

  // ---- mutations ----
  const createKnowledge = useMutation({
    mutationFn: (body: KnowledgeStateCreate) =>
      api.post<KnowledgeState>(`/projects/${projectId}/knowledge-states`, body),
    onSuccess: () => {
      toast("인지 상태를 기록했습니다.");
      refetchKnowledge();
    },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const updateKnowledge = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<KnowledgeState> }) =>
      api.patch<KnowledgeState>(`/projects/${projectId}/knowledge-states/${id}`, body),
    onSuccess: () => {
      toast("인지 상태를 수정했습니다.");
      refetchKnowledge();
    },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const deleteKnowledge = useMutation({
    mutationFn: (id: number) =>
      api.del(`/projects/${projectId}/knowledge-states/${id}`),
    onSuccess: () => {
      toast("인지 상태를 삭제했습니다.");
      refetchKnowledge();
    },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const createEvent = useMutation({
    mutationFn: (body: EventImpactCreate) =>
      api.post<EventImpact>(`/projects/${projectId}/event-impacts`, body),
    onSuccess: () => {
      toast("사건 영향을 기록했습니다.");
      refetchEvents();
    },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const updateEvent = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<EventImpact> }) =>
      api.patch<EventImpact>(`/projects/${projectId}/event-impacts/${id}`, body),
    onSuccess: () => {
      toast("사건 영향을 수정했습니다.");
      refetchEvents();
    },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const deleteEvent = useMutation({
    mutationFn: (id: number) =>
      api.del(`/projects/${projectId}/event-impacts/${id}`),
    onSuccess: () => {
      toast("사건 영향을 삭제했습니다.");
      refetchEvents();
    },
    onError: (e: Error) => toast(e.message, "error"),
  });

  // ---- target options ----
  const targetOptions = useMemo(() => {
    if (kTargetKind === "fact") {
      return (memories ?? [])
        .filter((m) => m.kind === "fact")
        .map((m) => ({ id: m.id, label: m.body.slice(0, 60) }));
    }
    if (kTargetKind === "foreshadow") {
      return (foreshadows ?? []).map((f) => ({ id: f.id, label: f.title }));
    }
    if (kTargetKind === "lore") {
      return (loreEntries ?? []).map((l) => ({ id: l.id, label: l.title }));
    }
    if (kTargetKind === "event") {
      return (eventImpacts ?? []).map((e) => ({ id: e.id, label: `${e.chapter_title ?? `회차 ${e.chapter_id}`} — ${e.label}` }));
    }
    return [];
  }, [kTargetKind, memories, foreshadows, loreEntries, eventImpacts]);

  // ---- submit handlers ----
  function submitKnowledge() {
    const body: KnowledgeStateCreate = {
      subject_type: kSubject,
      target_kind: kTargetKind,
      target_id: Number(kTargetId),
      status: kStatus,
    };
    if (kSubject === "character") {
      if (!kCharId) { toast("인물을 선택하세요.", "error"); return; }
      body.character_id = Number(kCharId);
    }
    if (kChapterId) body.revealed_chapter_id = Number(kChapterId);
    if (kSortOrder) body.effective_from_sort_order = Number(kSortOrder);
    if (!body.target_id || !Number.isFinite(body.target_id)) {
      toast("대상을 선택하세요.", "error"); return;
    }
    createKnowledge.mutate(body);
  }

  function submitEvent() {
    if (!eChapterId || !eLabel.trim()) {
      toast("회차와 사건명을 입력하세요.", "error"); return;
    }
    const body: EventImpactCreate = {
      chapter_id: Number(eChapterId),
      label: eLabel.trim(),
    };
    if (eCharDeltas.trim()) {
      try { body.character_deltas = JSON.parse(eCharDeltas); } catch { toast("인물 델타 JSON 오류", "error"); return; }
    }
    if (eRelDeltas.trim()) {
      try { body.relationship_deltas = JSON.parse(eRelDeltas); } catch { toast("관계 델타 JSON 오류", "error"); return; }
    }
    if (eFsDeltas.trim()) {
      try { body.foreshadow_deltas = JSON.parse(eFsDeltas); } catch { toast("복선 델타 JSON 오류", "error"); return; }
    }
    if (eStateAfter.trim()) body.state_after = eStateAfter.trim();
    createEvent.mutate(body);
  }

  // ---- timeline: event impacts sorted by chapter sort_order ----
  const timeline = useMemo(() => {
    return (eventImpacts ?? [])
      .slice()
      .sort((a, b) => (a.chapter_sort_order ?? 0) - (b.chapter_sort_order ?? 0) || a.id - b.id);
  }, [eventImpacts]);

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="mb-4 text-2xl font-bold">인지·사건 추적</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        작가/독자/인물별 인지 상태와 사건이 남긴 영향을 기록·추적합니다. 파생 job이 만든 초안은 승인 후에만 컨텍스트에 반영됩니다.
      </p>

      {/* tabs */}
      <div className="mb-4 flex gap-2" role="tablist" aria-label="인지·사건 보기">
        <Button
          variant={tab === "knowledge" ? "default" : "outline"}
          onClick={() => setTab("knowledge")}
          role="tab"
          aria-selected={tab === "knowledge"}
        >
          인지 상태
        </Button>
        <Button
          variant={tab === "events" ? "default" : "outline"}
          onClick={() => setTab("events")}
          role="tab"
          aria-selected={tab === "events"}
        >
          사건 영향
        </Button>
      </div>

      {tab === "knowledge" && (
        <>
          {/* create form */}
          <section className="mb-6 rounded-md border p-4">
            <h2 className="mb-3 font-semibold">인지 상태 기록</h2>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div>
                <Label htmlFor="knowledge-subject">주체</Label>
                <Select id="knowledge-subject" value={kSubject} onChange={(e) => setKSubject(e.target.value as KnowledgeSubjectType)}>
                  {SUBJECT_TYPES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                </Select>
              </div>
              {kSubject === "character" && (
                <div>
                  <Label htmlFor="knowledge-character">인물</Label>
                  <Select id="knowledge-character" value={kCharId} onChange={(e) => setKCharId(e.target.value)}>
                    <option value="">선택</option>
                    {(characters ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </Select>
                </div>
              )}
              <div>
                <Label htmlFor="knowledge-target-kind">대상 종류</Label>
                <Select
                  id="knowledge-target-kind"
                  value={kTargetKind}
                  onChange={(e) => {
                    setKTargetKind(e.target.value as KnowledgeTargetKind);
                    setKTargetId("");
                  }}
                >
                  {TARGET_KINDS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </Select>
              </div>
              <div>
                <Label htmlFor="knowledge-target">대상</Label>
                <Select id="knowledge-target" value={kTargetId} onChange={(e) => setKTargetId(e.target.value)}>
                  <option value="">선택</option>
                  {targetOptions.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
                </Select>
              </div>
              <div>
                <Label htmlFor="knowledge-status">상태</Label>
                <Select id="knowledge-status" value={kStatus} onChange={(e) => setKStatus(e.target.value as KnowledgeStatus)}>
                  {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                </Select>
              </div>
              <div>
                <Label htmlFor="knowledge-chapter">공개 회차</Label>
                <Select id="knowledge-chapter" value={kChapterId} onChange={(e) => setKChapterId(e.target.value)}>
                  <option value="">없음</option>
                  {(chapters ?? []).map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                </Select>
              </div>
              <div>
                <Label htmlFor="knowledge-sort-order">유효 시작 순서</Label>
                <Input id="knowledge-sort-order" inputMode="decimal" value={kSortOrder} onChange={(e) => setKSortOrder(e.target.value)} placeholder="sort_order" />
              </div>
            </div>
            <Button className="mt-3" onClick={submitKnowledge} disabled={createKnowledge.isPending}>
              기록
            </Button>
          </section>

          {/* filters */}
          <section className="mb-4 flex gap-3" aria-label="인지 상태 필터">
            <Select aria-label="주체 필터" value={fSubject} onChange={(e) => setFSubject(e.target.value)} className="w-32">
              <option value="">주체 전체</option>
              {SUBJECT_TYPES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </Select>
            <Select aria-label="공개 상태 필터" value={fVisibility} onChange={(e) => setFVisibility(e.target.value)} className="w-32">
              <option value="">상태 전체</option>
              {VISIBILITIES.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
            </Select>
          </section>

          {/* list */}
          <section>
            <h2 className="mb-2 font-semibold">기록된 인지 상태 ({knowledgeStates?.length ?? 0})</h2>
            <div className="space-y-2">
              {(knowledgeStates ?? []).map((k) => (
                <div key={k.id} className="flex items-start justify-between rounded-md border p-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{subjectLabel(k.subject_type)}</Badge>
                      {k.character_name && <Badge variant="secondary">{k.character_name}</Badge>}
                      <Badge variant="outline">{targetLabel(k.target_kind)}#{k.target_id}</Badge>
                      <Badge>{statusLabel(k.status)}</Badge>
                      <span className={visibilityClass(k.visibility)}>{k.visibility}</span>
                    </div>
                    {k.revealed_chapter_title && (
                      <p className="mt-1 text-xs text-muted-foreground">공개: {k.revealed_chapter_title}</p>
                    )}
                    {k.effective_from_sort_order != null && (
                      <p className="text-xs text-muted-foreground">유효 시작: {k.effective_from_sort_order}</p>
                    )}
                  </div>
                  <div className="flex gap-1">
                    {k.visibility === "draft" && (
                      <Button size="sm" variant="outline" onClick={() => updateKnowledge.mutate({ id: k.id, body: { visibility: "approved" } })}>
                        승인
                      </Button>
                    )}
                    {k.visibility === "approved" && (
                      <Button size="sm" variant="outline" onClick={() => updateKnowledge.mutate({ id: k.id, body: { visibility: "retired" } })}>
                        폐기
                      </Button>
                    )}
                    <Button size="sm" variant="destructive" onClick={() => deleteKnowledge.mutate(k.id)}>
                      삭제
                    </Button>
                  </div>
                </div>
              ))}
              {(knowledgeStates ?? []).length === 0 && (
                <p className="text-sm text-muted-foreground">기록된 인지 상태가 없습니다.</p>
              )}
            </div>
          </section>
        </>
      )}

      {tab === "events" && (
        <>
          {/* create form */}
          <section className="mb-6 rounded-md border p-4">
            <h2 className="mb-3 font-semibold">사건 영향 기록</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="event-chapter">회차</Label>
                <Select id="event-chapter" value={eChapterId} onChange={(e) => setEChapterId(e.target.value)}>
                  <option value="">선택</option>
                  {(chapters ?? []).map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                </Select>
              </div>
              <div>
                <Label htmlFor="event-label">사건명</Label>
                <Input id="event-label" value={eLabel} onChange={(e) => setELabel(e.target.value)} placeholder="예: 결투, 각성" />
              </div>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
              <div>
                <Label htmlFor="event-character-deltas">인물 델타 (JSON)</Label>
                <Textarea id="event-character-deltas" value={eCharDeltas} onChange={(e) => setECharDeltas(e.target.value)} placeholder='[{"character_id":1,"delta":"부상"}]' rows={2} />
              </div>
              <div>
                <Label htmlFor="event-relationship-deltas">관계 델타 (JSON)</Label>
                <Textarea id="event-relationship-deltas" value={eRelDeltas} onChange={(e) => setERelDeltas(e.target.value)} placeholder='[{"pair":[1,2],"from":"우호","to":"적대"}]' rows={2} />
              </div>
              <div>
                <Label htmlFor="event-foreshadow-deltas">복선 델타 (JSON)</Label>
                <Textarea id="event-foreshadow-deltas" value={eFsDeltas} onChange={(e) => setEFsDeltas(e.target.value)} placeholder='[{"foreshadow_id":3,"진전":"진행"}]' rows={2} />
              </div>
            </div>
            <div className="mt-3">
              <Label htmlFor="event-state-after">사건 직후 상태</Label>
              <Textarea id="event-state-after" value={eStateAfter} onChange={(e) => setEStateAfter(e.target.value)} placeholder="사건 직후 인물·복선 스냅샷" rows={2} />
            </div>
            <Button className="mt-3" onClick={submitEvent} disabled={createEvent.isPending}>
              기록
            </Button>
          </section>

          {/* timeline */}
          <section>
            <h2 className="mb-2 font-semibold">사건 영향 타임라인 ({timeline.length})</h2>
            <div className="space-y-3">
              {timeline.map((ev) => (
                <div key={ev.id} className="rounded-md border p-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{ev.chapter_title ?? `회차 ${ev.chapter_id}`}</Badge>
                        <span className="font-medium">{ev.label}</span>
                        <span className={visibilityClass(ev.visibility)}>{ev.visibility}</span>
                      </div>
                      {ev.state_after && (
                        <p className="mt-1 text-sm text-muted-foreground">{ev.state_after}</p>
                      )}
                      <div className="mt-2 space-y-1 text-xs">
                        {ev.character_deltas.length > 0 && (
                          <p>인물: {ev.character_deltas.map((d) => `${d.character_id ?? "?"}:${d.delta ?? ""}`).join(", ")}</p>
                        )}
                        {ev.relationship_deltas.length > 0 && (
                          <p>관계: {ev.relationship_deltas.map((d) => `${JSON.stringify(d.pair)} ${d.from ?? ""}→${d.to ?? ""}`).join(", ")}</p>
                        )}
                        {ev.foreshadow_deltas.length > 0 && (
                          <p>복선: {ev.foreshadow_deltas.map((d) => `${d.foreshadow_id ?? "?"}:${d["진전"] ?? ""}`).join(", ")}</p>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-1">
                      {ev.visibility === "draft" && (
                        <Button size="sm" variant="outline" onClick={() => updateEvent.mutate({ id: ev.id, body: { visibility: "approved" } })}>
                          승인
                        </Button>
                      )}
                      {ev.visibility === "approved" && (
                        <Button size="sm" variant="outline" onClick={() => updateEvent.mutate({ id: ev.id, body: { visibility: "retired" } })}>
                          폐기
                        </Button>
                      )}
                      <Button size="sm" variant="destructive" onClick={() => deleteEvent.mutate(ev.id)}>
                        삭제
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
              {timeline.length === 0 && (
                <p className="text-sm text-muted-foreground">기록된 사건 영향이 없습니다.</p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
