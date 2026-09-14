/**
 * 백엔드 /api/v1 fetch 클라이언트 — 사양 §5.
 * 인증 없음(로컬 단일 사용자). dev는 vite 프록시(/api → localhost:8000) 경유.
 */

const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function detailMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: init?.body ? { "content-type": "application/json" } : undefined,
      ...init,
    });
  } catch {
    throw new ApiError(
      0,
      "백엔드에 연결할 수 없습니다. 서버 실행 여부를 확인하세요.",
    );
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    let detail: unknown;
    try {
      const body = await res.json();
      detail = body?.detail;
      msg = detailMessage(detail) ?? msg;
    } catch {
      /* json 파싱 실패 시 기본 메시지 */
    }
    throw new ApiError(res.status, msg, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// ---- 도메인 타입 (backend/app/schemas.py 기준) ----

/** ChapterStatus = "초고" | "수정중" | "완료" */
export type ChapterStatus = "초고" | "수정중" | "완료";

/** D03-3 연재 상태 — 회차 집필 확정(confirmed)과 다른 수명주기 */
export type SerialState = "ongoing" | "hiatus" | "completed";

export interface Project {
  id: number;
  title: string;
  genre: string | null;
  synopsis: string | null;
  platform_note: string | null;
  style_profile?: string | null; // 문체 프로파일 (G-040)
  serial_state?: SerialState; // D03-3 연재 상태
  serial_completed_at?: string | null; // 완결 시각 (completed일 때만)
  ending_intent?: string | null; // D03-7 작품 수준 결말 후보
  ending_locked?: boolean; // D03-7 결말 잠금
  ending_updated_at?: string | null; // D03-7 결말 실제 변경 시각
  created_at: string;
  updated_at: string;
  /** 목록 카드용 집계 — 상세 조회에는 없을 수 있음 */
  chapter_count?: number;
  total_chars?: number;
}

export interface ProjectCreate {
  title: string;
  genre?: string | null;
  synopsis?: string | null;
  platform_note?: string | null;
}

export interface ProjectUpdate {
  title?: string;
  genre?: string | null;
  synopsis?: string | null;
  platform_note?: string | null;
  style_profile?: string | null;
  serial_state?: SerialState;
  ending_intent?: string | null;
  ending_locked?: boolean;
}

/** 권 표시 텍스트 — null(권 없음) 폴백 포함 */
export function volumeLabel(volume: number | null | undefined): string {
  return volume != null ? `${volume}권` : "권 없음";
}

/** 권 정렬 키 — null(권 없음)은 마지막에 배치 */
export function volumeSortKey(volume: number | null | undefined): number {
  return volume ?? Number.MAX_SAFE_INTEGER;
}

/** 회차 목록/트리용 (본문 제외) */
export interface Chapter {
  id: number;
  project_id: number;
  /** null = 권 없는 평면 회차 */
  volume: number | null;
  sort_order: number;
  title: string;
  status: ChapterStatus;
  word_count_cache: number;
  memo: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface ChapterDetail extends Chapter {
  content_md: string;
}

export type MemoryKind =
  | "summary"
  | "beat"
  | "decision"
  | "fact"
  | "timeline"
  | "relationship_note";
export type MemoryVisibility = "draft" | "approved" | "retired";

export interface MemoryEntry {
  id: number;
  project_id: number;
  chapter_id: number | null;
  source_revision: number | null;
  source_sha256: string;
  kind: MemoryKind;
  body: string;
  visibility: MemoryVisibility;
  effective_from_sort_order: number | null;
  effective_to_sort_order: number | null;
  provenance: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  stale: boolean;
  source_chapter_title: string | null;
  source_chapter_revision: number | null;
  source_chapter_sort_order: number | null;
}

export interface MemoryEntryCreate {
  chapter_id?: number | null;
  kind: MemoryKind;
  body: string;
  effective_from_sort_order?: number | null;
  effective_to_sort_order?: number | null;
}

export interface MemoryEntryUpdate {
  visibility?: MemoryVisibility;
  effective_from_sort_order?: number | null;
  effective_to_sort_order?: number | null;
}

export interface ChapterCreate {
  title?: string;
  volume?: number;
  sort_order?: number;
}

export interface ChapterUpdate {
  title?: string;
  volume?: number;
  sort_order?: number;
  status?: ChapterStatus;
  memo?: string | null;
}

export interface ChapterContentWrite {
  content_md: string;
  expected_revision: number;
}

export interface ChapterSnapshotMeta {
  id: number;
  chapter_id: number;
  revision: number;
  reason: "autosave" | "refine" | "scene_merge" | "restore" | string;
  created_at: string;
}

export interface ChapterSnapshotDetail extends ChapterSnapshotMeta {
  content_md: string;
}

export interface RevisionConflictDetail {
  code?: string;
  message?: string;
  current_revision?: number;
}

// ---- ChapterGoal (D01 회차 목표 영속화) ----
export type EpisodePurposeValue = "serial" | "volume_end" | "series_finale";

/** 저장용 목표 payload — 부분·빈 저장 허용, 서버가 trim/빈값 정규화 */
export interface ChapterGoalPayload {
  emotion_goal?: string | null;
  core_events?: string[] | null;
  character_choices?: string[] | null;
  cost?: string | null;
  prohibitions?: string[] | null;
  next_hook?: string | null;
  ending_intent?: string | null;
  scene_type?: string | null;
  target_chars_novelpia?: number | null;
}

export interface ChapterGoalVersion {
  goal_version: number;
  goal: ChapterGoalPayload;
  episode_purpose: EpisodePurposeValue;
  base_manuscript_revision: number | null;
  created_at: string;
  updated_at: string;
}

export interface ChapterGoalOut {
  chapter_id: number;
  project_id: number;
  /** null = 저장된 목표 없음(오류와 구분) */
  goal: ChapterGoalVersion | null;
  current_chapter_revision: number;
  history_count: number;
}

export interface ChapterGoalRevision {
  id: number;
  goal_version: number;
  goal: ChapterGoalPayload;
  episode_purpose: EpisodePurposeValue;
  base_manuscript_revision: number | null;
  restored_from: number | null;
  created_at: string;
}

export interface GoalConflictDetail {
  code?: string;
  message?: string;
  current_goal_version?: number | null;
}

// ---- ChapterFlow (D03-1 집필 흐름) ----
/** status(초고/수정중/완료)와 독립인 작업 흐름 단계. confirmed=집필 확정(연재 완결 아님) */
export type FlowStage = "planning" | "writing" | "revising" | "confirmed";

export interface ChapterFlowEvent {
  id: number;
  chapter_id: number;
  from_stage: FlowStage;
  to_stage: FlowStage;
  /** 전이 시점 저장본 목표 버전 참조 — 목표 내용이 아니다 */
  goal_version: number | null;
  manuscript_revision: number;
  created_at: string;
}

export interface ChapterFlowOut {
  chapter_id: number;
  project_id: number;
  flow_stage: FlowStage;
  last_event: ChapterFlowEvent | null;
  current_goal_version: number | null;
  current_chapter_revision: number;
}

// ---- ChapterResume (D03-2 재개 계약) — 순수 파생 읽기 ----
export interface ChapterResumeScene {
  id: number;
  sort_order: number;
  title: string;
}

export interface ChapterResumeOut {
  chapter_id: number;
  project_id: number;
  flow_stage: FlowStage;
  last_event: ChapterFlowEvent | null;
  current_goal_version: number | null;
  current_chapter_revision: number;
  /** last_event 앵커 대비 목표 버전·원고 revision 변경 여부 */
  goal_changed_since_transition: boolean;
  manuscript_changed_since_transition: boolean;
  /** accepted=false 윤문 실행 수 (거절/미적용 구분 불가는 기존 스키마 한계) */
  pending_refine_runs: number;
  /** 본문이 비어 있는 첫 장면 — 없으면 null */
  next_scene: ChapterResumeScene | null;
  scene_count: number;
}

// ---- EvidenceLinks (D03-4 근거 연결) ----
/** 목표 필드(사건/선택/대가) ↔ 원문 발췌의 수동 링크 — 자동 판정 없음 */
export type EvidenceLinkField = "core_events" | "character_choices" | "cost";
export type EvidenceManuscriptStatus = "intact" | "broken";
export type EvidenceGoalStatus = "unchanged" | "drifted" | "goal_deleted";

export interface EvidenceLink {
  id: number;
  chapter_id: number;
  goal_field: EvidenceLinkField;
  item_index: number | null;
  /** 링크 생성 시점의 목표 항목 스냅샷 — 드리프트 비교 기준 */
  goal_item_text: string;
  excerpt: string;
  /** 링크 생성 시점의 목표 버전 앵커 */
  goal_version: number;
  current_goal_version: number | null;
  manuscript_status: EvidenceManuscriptStatus;
  goal_status: EvidenceGoalStatus;
  created_at: string;
}

export interface EvidenceLinkList {
  chapter_id: number;
  links: EvidenceLink[];
}

// ---- Character / Relationship (Sprint 2 M2) ----
export type CharacterRole = "주연" | "조연" | "단역" | "기타";

export interface Character {
  id: number;
  project_id: number;
  name: string;
  aliases: string[] | null;
  role: CharacterRole | null;
  appearance: string | null;
  personality: string | null;
  speech_style: string | null;
  background: string | null;
  card_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CharacterCreate {
  name: string;
  aliases?: string[] | null;
  role?: CharacterRole | null;
  appearance?: string | null;
  personality?: string | null;
  speech_style?: string | null;
  background?: string | null;
}

export interface CharacterUpdate
  extends Partial<Omit<CharacterCreate, "name">> {
  name?: string;
}

export interface Relationship {
  id: number;
  from_character_id: number;
  to_character_id: number;
  label: string | null;
  note: string | null;
}

// ---- LoreEntry (Sprint 2 M3) ----
export type LoreCategory = "용어" | "장소" | "세력" | "기타";

export interface LoreEntry {
  id: number;
  project_id: number;
  category: LoreCategory;
  title: string;
  content: string | null;
  keywords: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface LoreEntryCreate {
  category: LoreCategory;
  title: string;
  content?: string | null;
  keywords?: string[] | null;
}

export interface LoreEntryUpdate {
  category?: LoreCategory;
  title?: string;
  content?: string | null;
}

// ---- PromptPreset (M4) ----
export type ContextFlag = "chapter" | "characters" | "lore";

export interface PromptPreset {
  id: number;
  name: string;
  template_text: string;
  context_flags: ContextFlag[] | null;
}

export interface PromptPresetCreate {
  name: string;
  template_text: string;
  context_flags?: ContextFlag[] | null;
}

// ---- Project Bootstrap (입력 하나로 작품 전체 구조 AI 생성) ----
/** A-038 GET /projects/{pid}/plus-status — 노벨피아 PLUS 충족 현황 (F-033) */
export interface PlusStatus {
  chapter_count: number;
  chapter_count_met: boolean;
  done_chapter_count: number;
  done_chapters_3000: number;
  done_chars_met: boolean;
  eligible: boolean;
}

export interface BootstrapRequest {
  genre: string;
  premise?: string | null;
  volume_count?: number;
  chapters_per_volume?: number;
  title_style?: string;
  use_ai?: boolean;
}

export interface BootstrapResponse {
  project_id: number;
  title: string;
  logline: string;
  outline_summary: string;
  character_count: number;
  lore_count: number;
  chapter_count: number;
  volume_count: number;
  relationship_count: number;
  volume_note_count?: number; // 권 개요 동시 생성 수 (G-050)
  first_chapter_id?: number | null;
  title_candidates: string[];
  theme: string | null;
  used_ai: boolean;
  fallback: boolean;
}

/** 작품 준비 확인 후 다음 빈 회차를 자동 집필·저장하는 응답 */
export interface AssistantGenerateNextResponse {
  project_id: number;
  chapter_id: number;
  chapter_title: string;
  revision: number;
  content_md: string;
  word_count_cache: number;
}

// ---- Refine (Sprint 3 M5) — taxonomy ID A~J span ----
export type RefineRoute = "light" | "standard" | "heavy";
export type TaxonomyCategory =
  | "A"
  | "B"
  | "C"
  | "D"
  | "E"
  | "F"
  | "G"
  | "H"
  | "I"
  | "J";

export interface RefineSpan {
  category: TaxonomyCategory;
  start: number;
  end: number;
  severity: "info" | "warn";
  message: string | null;
}

export interface RefineResult {
  run_id: number;
  base_revision: number;
  route_hint: string;
  spans: RefineSpan[];
  original: string;
  refined: string;
  changed_ratio: number;
  gate: "pass" | "warn" | "block";
  status: "ok" | "blocked";
}

// ---- FinalEdition (D03-6 완결본 관리) ----

export interface FinalEditionChapterEntry {
  chapter_id: number;
  title: string;
  sort_order: number;
  revision: number;
  flow_stage: string;
  status: string;
  chars: number;
}

export interface FinalEdition {
  id: number;
  project_id: number;
  label: string | null;
  created_at: string;
  serial_state: SerialState;
  chapter_count: number;
  total_chars: number;
}

export interface FinalEditionDetail extends FinalEdition {
  manifest: FinalEditionChapterEntry[];
  content_md: string;
  checklist: CompletionChecklist;
}

export interface CompletionChecklist {
  serial_state: SerialState;
  serial_completed_at: string | null;
  chapters: {
    total: number;
    by_stage: Record<string, number>;
    unconfirmed: number;
  };
  foreshadows: {
    total: number;
    open: Array<{ id: number; title: string; status: string }>;
    by_disposition: Record<string, number>;
  };
  pending_refine_runs: number;
  broken_evidence_links: number;
  finale_goals_missing_ending: Array<{ chapter_id: number; title: string }>;
}

// ---- EndingImpact (D03-7 결말 변경 영향) ----

export interface EndingImpact {
  ending_intent: string | null;
  ending_locked: boolean;
  ending_updated_at: string | null;
  open_foreshadows: Array<{ id: number; title: string }>;
  stale_goal_chapters: Array<{
    chapter_id: number;
    title: string;
    goal_version: number;
  }>;
  finale_chapters: Array<{
    chapter_id: number;
    title: string;
    has_ending_intent: boolean;
  }>;
}
