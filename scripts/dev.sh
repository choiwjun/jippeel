#!/usr/bin/env bash
# Jippeel 대시보드 통합 실행 스크립트 (WSL)
# 용도: 백엔드(uvicorn:8000) + 프론트(vite:5173) 기동 → 브라우저 오픈
set -u
PROJ="/mnt/c/Users/wj941/Documents/jippeel"
BUILD="$PROJ/frontend"
LOG_DIR="$HOME/.jippeel-logs"
mkdir -p "$LOG_DIR"
BACKEND_PORT="${JIPPEEL_BACKEND_PORT:-8000}"
FRONTEND_PORT="${JIPPEEL_FRONTEND_PORT:-5173}"
BACKEND_HOST="${JIPPEEL_BACKEND_HOST:-0.0.0.0}"
WSL_GATEWAY="$(ip route 2>/dev/null | awk '/^default/ {print $3; exit}')"
WSL_GATEWAY="${WSL_GATEWAY:-127.0.0.1}"
BACKEND_PROXY_URL="${JIPPEEL_BACKEND_URL:-http://$WSL_GATEWAY:$BACKEND_PORT}"

# 백엔드는 Windows venv의 python.exe로 뜬다. WSL과 Windows의 localhost가
# 다를 수 있으므로 health probe는 curl.exe도 시도하고, 프록시는 WSL gateway를 사용한다.
backend_up() {
   curl -sf --max-time 2 "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1 || {
      command -v curl.exe >/dev/null 2>&1 && \
         curl.exe -sf --max-time 2 "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1
   }
}
windows_listeners() {
   if command -v netstat.exe >/dev/null 2>&1; then
      netstat.exe -ano 2>/dev/null | tr -d '\r' | awk -v needle=":$1" \
         '$1 == "TCP" && index($2, needle) == length($2) - length(needle) + 1 { print $2 }'
   fi
}
port_up() {
   ss -tln 2>/dev/null | grep -q ":$1 " || [ -n "$(windows_listeners "$1")" ]
}
has_lan_listener() {
   printf '%s\n' "$1" | grep -Eq "(^|[[:space:]])(0\\.0\\.0\\.0|\\*|\\[::\\]):$BACKEND_PORT($|[[:space:]])"
}

# 1) 백엔드
if backend_up; then
   WINDOWS_BACKEND_LISTENERS="$(windows_listeners "$BACKEND_PORT")"
   if [ "$BACKEND_HOST" = "0.0.0.0" ] && [ -n "$WINDOWS_BACKEND_LISTENERS" ] && \
      ! has_lan_listener "$WINDOWS_BACKEND_LISTENERS"; then
      echo "[경고] :$BACKEND_PORT에 기존 localhost 전용 서버가 실행 중입니다."
      echo "       기존 Jippeel을 종료한 뒤 scripts/dev.sh를 다시 실행하세요."
      exit 1
   fi
   echo "[backend] 이미 실행 중 (:$BACKEND_PORT)"
elif port_up "$BACKEND_PORT"; then
   echo "[경고] :$BACKEND_PORT를 다른 프로세스가 점유 중이고 /health 응답이 없습니다."
   echo "       movestudio 등 다른 프로젝트의 서버일 수 있으니 확인 후 정리하세요."
else
   echo "[backend] uvicorn 기동..."
   # 윤문 스텁: prod.sh와 동일 — Windows python.exe라 cmd에 cp가 없어
   # PowerShell Copy-Item을 쓰고, WSLENV로 두 변수를 Windows에 전달한다.
   (cd "$PROJ/backend" && setsid nohup env \
      IM_NOT_AI_DIAGNOSE_CMD='powershell -NoProfile -Command "Copy-Item -LiteralPath {input} -Destination {diagnosis}"' \
      IM_NOT_AI_REFINE_CMD='powershell -NoProfile -Command "Copy-Item -LiteralPath {input} -Destination {output}"' \
      WSLENV="IM_NOT_AI_DIAGNOSE_CMD:IM_NOT_AI_REFINE_CMD${WSLENV:+:$WSLENV}" \
      .venv/Scripts/python.exe -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
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
if port_up "$FRONTEND_PORT"; then
   echo "[frontend] 이미 실행 중 (:$FRONTEND_PORT)"
else
   echo "[frontend] vite 기동..."
   (cd "$BUILD" && setsid nohup env JIPPEEL_BACKEND_URL="$BACKEND_PROXY_URL" \
      npx vite --host --port "$FRONTEND_PORT" --strictPort \
      >"$LOG_DIR/frontend.log" 2>&1 </dev/null &)
   for i in $(seq 1 40); do
      port_up "$FRONTEND_PORT" && break
      sleep 1
   done
   port_up "$FRONTEND_PORT" && echo "[frontend] OK" || {
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

echo "[done] http://localhost:$FRONTEND_PORT"
command -v cmd.exe >/dev/null && cmd.exe /c start "" "http://localhost:$FRONTEND_PORT" 2>/dev/null
