import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useAuthStore } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * LAN 인증 게이트 — JIPPEEL_LAN_AUTH=1일 때만 로그인 화면을 띄운다.
 *
 * - 앱 부팅 시 /auth/status로 활성 여부를 조회한다.
 * - 인증 필요(401) 시 전체 화면 로그인 폼으로 전환한다.
 * - 비활성(기본 로컬 dev)이면 children을 그대로 렌더한다.
 */
export function LoginGate({ children }: { children: ReactNode }) {
  const { status, needsLogin, checking, error, checkStatus, login } =
    useAuthStore();
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void checkStatus();
  }, [checkStatus]);

  // auth 비활성이거나 상태를 모르면 그대로 통과(로컬 dev 무간섭)
  if (!status?.enabled && !needsLogin) return <>{children}</>;
  if (status?.enabled && !needsLogin && !checking) return <>{children}</>;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!password || submitting) return;
    setSubmitting(true);
    try {
      await login(password);
    } finally {
      setSubmitting(false);
      setPassword("");
    }
  };

  return (
    <div className="flex h-full items-center justify-center bg-background">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg border border-border bg-card p-6 shadow-lg"
        aria-label="LAN 로그인"
      >
        <div className="space-y-1">
          <h1 className="text-lg font-semibold tracking-tight">Jippeel</h1>
          <p className="text-sm text-muted-foreground">
            이 네트워크 공유 인스턴스는 비밀번호로 보호됩니다.
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="lan-password">비밀번호</Label>
          <Input
            id="lan-password"
            type="password"
            autoComplete="current-password"
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
          />
        </div>
        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}
        <Button type="submit" className="w-full" disabled={!password || submitting}>
          {submitting ? "확인 중…" : "로그인"}
        </Button>
      </form>
    </div>
  );
}
