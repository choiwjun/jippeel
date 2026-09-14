#!/usr/bin/env bash
# Jippeel 운영 모드 실행 (A-040) — uvicorn 단일 프로세스가 API + 프론트(dist) 서빙
# 용도: Jippeel실행.bat에서 호출. dev 모드(scripts/dev.sh, vite :5173)와 별개.
set -u
PROJ="/mnt/c/Users/wj941/Documents/jippeel"
LOG_DIR="$HOME/.jippeel-logs"
mkdir -p "$LOG_DIR"
DIST="$PROJ/frontend/dist"
APP_HOST="${JIPPEEL_HOST:-0.0.0.0}"
APP_PORT="${JIPPEEL_PORT:-8000}"

if [ ! -f "$DIST/index.html" ]; then
  echo "[prod] frontend/dist 없음 — 먼저 프론트를 빌드하세요 (frontend: npm run build)"
  exit 1
fi

# GPT OAuth 브릿지 — 죽어 있으면 자동 재기동한다(credential은 브릿지 소유).
bridge_up() {
  curl -sf --max-time 2 "http://127.0.0.1:10531/v1/models" >/dev/null 2>&1
}
if ! bridge_up; then
  echo "[llm] GPT OAuth 브릿지 기동 (npx openai-oauth --detach)..."
  npx openai-oauth --detach >/dev/null 2>&1 || true
  for i in $(seq 1 15); do bridge_up && break; sleep 1; done
  bridge_up || echo "[경고] 브릿지 미응답 — 최초 1회 'npx openai-oauth login' 필요"
fi

# 백엔드는 Windows venv의 python.exe로 뜨므로 리스너는 Windows 측이다.
# WSL의 curl/ss가 Windows 포트를 보지 못할 수 있어 curl.exe와 netstat.exe도
# 함께 사용한다. health probe는 127.0.0.1(IPv4)로 고정한다.
backend_up() {
  curl -sf --max-time 2 "http://127.0.0.1:$APP_PORT/health" >/dev/null 2>&1 || {
    command -v curl.exe >/dev/null 2>&1 && \
      curl.exe -sf --max-time 2 "http://127.0.0.1:$APP_PORT/health" >/dev/null 2>&1
  }
}

windows_listeners() {
  if command -v netstat.exe >/dev/null 2>&1; then
    netstat.exe -ano 2>/dev/null | tr -d '\r' | awk -v needle=":$APP_PORT" '
      $1 == "TCP" && index($2, needle) == length($2) - length(needle) + 1 { print $2 }
    '
  fi
}

has_lan_listener() {
  printf '%s\n' "$1" | grep -Eq "(^|[[:space:]])(0\\.0\\.0\\.0|\\*|\\[::\\]):$APP_PORT($|[[:space:]])"
}

WIN_LISTENERS="$(windows_listeners)"

if backend_up; then
  if [ "$APP_HOST" = "0.0.0.0" ] && [ -n "$WIN_LISTENERS" ] && ! has_lan_listener "$WIN_LISTENERS"; then
    echo "[경고] :$APP_PORT에 기존 localhost 전용 서버가 실행 중입니다."
    echo "       기존 Jippeel을 종료한 뒤 Jippeel실행.bat을 다시 실행하세요."
    exit 1
  fi
  echo "[backend] 이미 실행 중 (:$APP_PORT)"
elif [ -n "$WIN_LISTENERS" ]; then
  echo "[경고] :$APP_PORT가 이미 사용 중입니다 ($WIN_LISTENERS)."
  echo "       기존 프로세스를 확인·종료한 뒤 Jippeel실행.bat을 다시 실행하세요."
  exit 1
else
  echo "[backend] uvicorn 기동 (정적 서빙 포함 — $APP_HOST:$APP_PORT)..."
  (cd "$PROJ/backend" && setsid nohup env \
     IM_NOT_AI_DIAGNOSE_CMD='cp {input} {diagnosis}' \
     IM_NOT_AI_REFINE_CMD='cp {input} {output}' \
     JIPPEEL_REVIEW_PROVIDER="${JIPPEEL_REVIEW_PROVIDER:-agy}" \
     JIPPEEL_AGY_MODEL="${JIPPEEL_AGY_MODEL:-gemini-3.8-flash-high}" \
     WSLENV="JIPPEEL_REVIEW_PROVIDER:JIPPEEL_AGY_MODEL${WSLENV:+:$WSLENV}" \
     .venv/Scripts/python.exe -m uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT" \
     > "$LOG_DIR/backend-prod.log" 2>&1 < /dev/null &)
  for i in $(seq 1 30); do backend_up && break; sleep 1; done
  backend_up || { echo "[backend] 실패 — $LOG_DIR/backend-prod.log 확인"; exit 1; }
  echo "[backend] OK"
fi

echo "[done] A PC: http://127.0.0.1:$APP_PORT"

# Windows 호스트의 사설 IPv4 주소를 안내한다. WSL 내부 IP는 다른 PC에서
# 접근할 주소가 아닐 수 있으므로 Windows 네트워크 어댑터 주소를 우선 표시한다.
if [ "$APP_HOST" = "0.0.0.0" ] && command -v ipconfig.exe >/dev/null 2>&1; then
  LAN_IPS=$(ipconfig.exe 2>/dev/null | tr -d '\r' | awk -F: '/IPv4/ {
    gsub(/^[[:space:]]+/, "", $2)
    if ($2 ~ /^[0-9]+\./ && $2 !~ /^127\./ && $2 !~ /^169\.254\./) print $2
  }' | sort -u)
  if [ -n "$LAN_IPS" ]; then
    echo "[B PC] 같은 네트워크에서 아래 주소로 접속하세요:"
    while IFS= read -r ip; do
      [ -n "$ip" ] && echo "        http://$ip:$APP_PORT"
    done <<EOF
$LAN_IPS
EOF
    echo "        (Windows 방화벽에서 사설 네트워크 TCP $APP_PORT 허용 필요)"
  else
    echo "[B PC] A PC의 사설 IPv4 주소를 확인해 http://<A-PC-IP>:$APP_PORT 로 접속하세요."
  fi
else
  echo "[B PC] http://<A-PC-IP>:$APP_PORT 로 접속하세요."
fi

echo "[주의] 이 앱은 현재 로그인 기능이 없으므로 인터넷에 포트포워딩하지 마세요."
command -v cmd.exe >/dev/null && cmd.exe /c start "" "http://127.0.0.1:$APP_PORT" 2>/dev/null
