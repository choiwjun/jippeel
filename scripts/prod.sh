#!/usr/bin/env bash
# Jippeel 운영 모드 실행 (A-040) — uvicorn 단일 프로세스가 API + 프론트(dist) 서빙
# 용도: Jippeel실행.bat에서 호출. dev 모드(scripts/dev.sh, vite :5173)와 별개.
set -u
PROJ="/mnt/c/Users/wj941/OneDrive/바탕 화면/WJproject/jippeel"
LOG_DIR="$HOME/.jippeel-logs"
mkdir -p "$LOG_DIR"
DIST="$PROJ/frontend/dist"

if [ ! -f "$DIST/index.html" ]; then
  echo "[prod] frontend/dist 없음 — 먼저 프론트를 빌드하세요 (frontend: npm run build)"
  exit 1
fi

port_up() { ss -tln 2>/dev/null | grep -q ":$1 "; }

if port_up 8000; then
  echo "[backend] 이미 실행 중 (:8000)"
else
  echo "[backend] uvicorn 기동 (정적 서빙 포함 — http://localhost:8000)..."
  (cd "$PROJ/backend" && setsid nohup env \
     IM_NOT_AI_DIAGNOSE_CMD='cp {input} {diagnosis}' \
     IM_NOT_AI_REFINE_CMD='cp {input} {output}' \
     .venv/bin/python -m uvicorn app.main:app --port 8000 \
     > "$LOG_DIR/backend-prod.log" 2>&1 < /dev/null &)
  for i in $(seq 1 30); do curl -sf http://localhost:8000/health >/dev/null && break; sleep 1; done
  curl -sf http://localhost:8000/health >/dev/null || { echo "[backend] 실패 — $LOG_DIR/backend-prod.log 확인"; exit 1; }
  echo "[backend] OK"
fi

echo "[done] http://localhost:8000"
command -v cmd.exe >/dev/null && cmd.exe /c start "" "http://localhost:8000" 2>/dev/null
