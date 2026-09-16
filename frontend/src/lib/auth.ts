/**
 * LAN 인증 클라이언트 — backend /api/v1/auth 계약.
 *
 * JIPPEEL_LAN_AUTH=1일 때만 활성화된다. 세션은 서명된 httponly 쿠키로
 * 유지되므로 프론트는 토큰을 직접 다루지 않는다.
 * - GET /auth/status  → { enabled, configured }
 * - POST /auth/login  → 200 { enabled, authenticated } | 401
 * - POST /auth/logout → 200 { ok }
 *
 * 401 처리: api.request가 ApiError(401)을 던지면 authStore가 로그인
 * 화면을 띄운다. 스트림(fetch) 경로도 동일하게 처리한다.
 */
import { create } from "zustand";

const BASE = "/api/v1/auth";

export interface AuthStatus {
  enabled: boolean;
  configured: boolean;
}

interface AuthState {
  /** null = 아직 모름(초기 로딩) */
  status: AuthStatus | null;
  /** 로그인 필요 — 401을 받았거나 enabled인데 미인증 */
  needsLogin: boolean;
  checking: boolean;
  error: string | null;

  checkStatus: () => Promise<void>;
  login: (password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  /** api 클라이언트가 401을 받았을 때 호출 */
  requireLogin: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  status: null,
  needsLogin: false,
  checking: false,
  error: null,

  checkStatus: async () => {
    set({ checking: true, error: null });
    try {
      const res = await fetch(`${BASE}/status`, { credentials: "same-origin" });
      if (!res.ok) throw new Error(`status ${res.status}`);
      const status = (await res.json()) as AuthStatus;
      set({ status, checking: false, needsLogin: status.enabled && get().needsLogin });
    } catch {
      // status 조회 실패는 인증 비활성(로컬 dev)으로 간주해 앱을 막지 않는다.
      set({ status: { enabled: false, configured: false }, checking: false });
    }
  },

  login: async (password) => {
    set({ error: null });
    try {
      const res = await fetch(`${BASE}/login`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ password }),
      });
      if (res.status === 401) {
        set({ error: "비밀번호가 올바르지 않습니다." });
        return false;
      }
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        set({ error: typeof j?.detail === "string" ? j.detail : `로그인 실패 (HTTP ${res.status})` });
        return false;
      }
      set({ needsLogin: false, error: null });
      return true;
    } catch {
      set({ error: "백엔드에 연결할 수 없습니다." });
      return false;
    }
  },

  logout: async () => {
    try {
      await fetch(`${BASE}/logout`, { method: "POST", credentials: "same-origin" });
    } finally {
      set({ needsLogin: true });
    }
  },

  requireLogin: () => {
    set({ needsLogin: true });
  },
}));

/** 401 응답을 받았을 때 호출 — auth 활성 상태면 로그인 화면을 연다. */
export function notifyUnauthorized() {
  useAuthStore.getState().requireLogin();
}
