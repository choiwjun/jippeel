#!/usr/bin/env bash
# Jippeel 운영 모드 실행 (A-040) — uvicorn 단일 프로세스가 API + 프론트(dist) 서빙
# 용도: Jippeel실행.bat에서 호출. dev 모드(scripts/dev.sh, vite :5173)와 별개.
set -u
PROJ="/mnt/c/Users/wj941/Documents/jippeel"
LOG_DIR="$HOME/.jippeel-logs"
mkdir -p "$LOG_DIR"
DIST="$PROJ/frontend/dist"

if [ ! -f "$DIST/index.html" ]; then
  echo "[prod] frontend/dist 없음 — 먼저 프론트를 빌드하세요 (frontend: npm run build)"
  exit 1
fi

# 백엔드는 Windows venv의 python.exe로 뜨므로 리스너는 Windows 측이다.
# WSL의 ss는 Windows 포트를 보지 못하고, localhost는 ::1로 해석돼 IPv4-only
# 리스너에 실패한다 — 127.0.0.1(IPv4) health probe로 판정한다.
backend_up() { curl -sf --max-time 2 http://127.0.0.1:8000/health >/dev/null 2>&1; }

if backend_up; then
  echo "[backend] 이미 실행 중 (:8000)"
else
  echo "[backend] uvicorn 기동 (정적 서빙 포함 — http://localhost:8000)..."
  (cd "$PROJ/backend" && setsid nohup env \
     IM_NOT_AI_DIAGNOSE_CMD='cp {input} {diagnosis}' \
     IM_NOT_AI_REFINE_CMD='cp {input} {output}' \
     .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 \
     > "$LOG_DIR/backend-prod.log" 2>&1 < /dev/null &)
  for i in $(seq 1 30); do backend_up && break; sleep 1; done
  backend_up || { echo "[backend] 실패 — $LOG_DIR/backend-prod.log 확인"; exit 1; }
  echo "[backend] OK"
fi

echo "[done] http://localhost:8000"
command -v cmd.exe >/dev/null && cmd.exe /c start "" "http://localhost:8000" 2>/dev/null
