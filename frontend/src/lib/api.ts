/**
 * 백엔드 /api/v1 fetch 클라이언트 — 사양 §5.
 * 인증 없음(로컬 단일 사용자). dev는 vite 프록시(/api → localhost:8000) 경유.
 */

const BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function detailMessage(detail: unknown): string | null {
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === 'string') return message;
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: init?.body ? { 'content-type': 'application/json' } : undefined,
      ...init,
    });
  } catch {
    throw new ApiError(0, '백엔드에 연결할 수 없습니다. 서버 실행 여부를 확인하세요.');
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    let detail: unknown;
    try {
      const body = await res.json();
      detail = body?.detail;
      msg = detailMessage(detail) ?? msg;
    } catch { /* json 파싱 실패 시 기본 메시지 */ }
    throw new ApiError(res.status, msg, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

// ---- 도메인 타입 (backend/app/schemas.py 기준) ----

/** ChapterStatus = "초고" | "수정중" | "완료" */
export type ChapterStatus = '초고' | '수정중' | '완료';

export interface Project {
  id: number;
  title: string;
  genre: string | null;
  synopsis: string | null;
  platform_note: string | null;
  style_profile?: string | null;  // 문체 프로파일 (G-040)
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

/** 권 표시 텍스트 — null(권 없음) 폴백 포함 */
export function volumeLabel(volume: number | null | undefined): string {
  return volume != null ? `${volume}권` : '권 없음';
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
  reason: 'autosave' | 'refine' | 'scene_merge' | 'restore' | string;
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


// ---- Character / Relationship (Sprint 2 M2) ----
export type CharacterRole = '주연' | '조연' | '단역' | '기타';

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

export interface CharacterUpdate extends Partial<Omit<CharacterCreate, 'name'>> {
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
export type LoreCategory = '용어' | '장소' | '세력' | '기타';

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

// ---- AiEndpoint / PromptPreset (Sprint 3 M4) ----
export interface AiEndpoint {
  /** NFR-202 — api_key 평문은 응답에 절대 없음. has_api_key 플래그만 노출 */
  id: number;
  name: string;
  base_url: string;
  default_model: string | null;
  /** null이면 요청에 temperature를 전송하지 않음 — Codex 계열 모델이 거부 */
  temperature: number | null;
  /** 미설정(null)이면 전송하지 않음 — minimal|low|medium|high|xhigh */
  reasoning_effort: string | null;
  is_default: boolean;
  has_api_key: boolean;
}

export interface AiEndpointCreate {
  name: string;
  base_url: string;
  api_key?: string | null;
  default_model?: string | null;
  temperature?: number | null;
  reasoning_effort?: string | null;
  is_default?: boolean;
}

export interface AiEndpointUpdate {
  name?: string;
  base_url?: string;
  api_key?: string | null;
  default_model?: string | null;
  temperature?: number | null;
  reasoning_effort?: string | null;
  is_default?: boolean;
}

export type ContextFlag = 'chapter' | 'characters' | 'lore';

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
  volume_note_count?: number;  // 권 개요 동시 생성 수 (G-050)
  title_candidates: string[];
  theme: string | null;
  used_ai: boolean;
  fallback: boolean;
}

// ---- Refine (Sprint 3 M5) — taxonomy ID A~J span ----
export type RefineRoute = 'light' | 'standard' | 'heavy';
export type TaxonomyCategory = 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J';

export interface RefineSpan {
  category: TaxonomyCategory;
  start: number;
  end: number;
  severity: 'info' | 'warn';
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
  gate: 'pass' | 'warn' | 'block';
  status: 'ok' | 'blocked';
}
