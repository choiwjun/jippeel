#!/usr/bin/env bash
# Jippeel 대시보드 통합 실행 스크립트 (WSL)
# 용도: 백엔드(uvicorn:8000) + 프론트(vite:5173) 기동 → 브라우저 오픈
set -u
PROJ="/mnt/c/Users/wj941/Documents/jippeel"
BUILD="$PROJ/frontend"
LOG_DIR="$HOME/.jippeel-logs"
mkdir -p "$LOG_DIR"

# 백엔드는 Windows venv의 python.exe로 뜬다 — WSL의 ss는 Windows 포트를 보지 못하고
# localhost는 ::1로 해석돼 IPv4-only 리스너에 실패하므로 127.0.0.1 health probe로 판정.
backend_up() { curl -sf --max-time 2 http://127.0.0.1:8000/health >/dev/null 2>&1; }
port_up() { ss -tln 2>/dev/null | grep -q ":$1 "; }

# 1) 백엔드
if backend_up; then
   echo "[backend] 이미 실행 중 (:8000)"
elif port_up 8000; then
   echo "[경고] :8000을 다른 프로세스가 점유 중이고 /health 응답이 없습니다."
   echo "       movestudio 등 다른 프로젝트의 서버일 수 있으니 확인 후 정리하세요."
else
   echo "[backend] uvicorn 기동..."
   (cd "$PROJ/backend" && setsid nohup env \
      IM_NOT_AI_DIAGNOSE_CMD='cp {input} {diagnosis}' \
      IM_NOT_AI_REFINE_CMD='cp {input} {output}' \
      .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 \
      >"$LOG_DIR/backend.log" 2>&1 </dev/null &)
   for i in $(seq 1 30); do
      backend_up && break
      sleep 1
   done
   backend_up && echo "[backend] OK" || {
      echo "[backend] 실패 — $LOG_DIR/backend.log 확인"
      exit 1
   }
fi

# 2) 프론트 (빠른 ext4 빌드 디렉터리 사용)
if port_up 5173; then
   echo "[frontend] 이미 실행 중 (:5173)"
else
   echo "[frontend] vite 기동..."
   (cd "$BUILD" && setsid nohup npx vite --host --port 5173 --strictPort \
      >"$LOG_DIR/frontend.log" 2>&1 </dev/null &)
   for i in $(seq 1 40); do
      port_up 5173 && break
      sleep 1
   done
   port_up 5173 && echo "[frontend] OK" || {
      echo "[frontend] 실패 — $LOG_DIR/frontend.log 확인"
      exit 1
   }
fi

# 3) GPT OAuth 브릿지 확인 — 계정/토큰은 openai-oauth가 관리한다.
# 이 스크립트는 로그인·실제 provider 호출·자동 endpoint 등록을 하지 않는다.
if port_up 10531; then
   echo "[llm] GPT OAuth 브릿지 확인 (:10531)"
else
   echo "[llm] GPT OAuth 브릿지 미실행"
   echo "       최초 1회: npx openai-oauth login"
   echo "       기동:     npx openai-oauth --detach"
fi

echo "[done] http://localhost:5173"
command -v cmd.exe >/dev/null && cmd.exe /c start "" "http://localhost:5173" 2>/dev/null
