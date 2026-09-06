#!/usr/bin/env bash
# Jippeel 대시보드 통합 실행 스크립트 (WSL)
# 용도: 백엔드(uvicorn:8000) + 프론트(vite:5173) 기동 → 브라우저 오픈
set -u
PROJ="/mnt/c/Users/wj941/OneDrive/바탕 화면/WJproject/jippeel"
BUILD="$HOME/jippeel-build/frontend"
LOG_DIR="$HOME/.jippeel-logs"
mkdir -p "$LOG_DIR"

port_up() { ss -tln 2>/dev/null | grep -q ":$1 "; }

# 1) 백엔드
if port_up 8000; then
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "[backend] 이미 실행 중 (:8000)"
  else
    echo "[경고] :8000을 다른 프로세스가 점유 중이고 /health 응답이 없습니다."
    echo "       movestudio 등 다른 프로젝트의 서버일 수 있으니 확인 후 정리하세요:"
    echo "       ss -tlnp | grep :8000"
  fi
else
  echo "[backend] uvicorn 기동..."
  (cd "$PROJ/backend" && setsid nohup env \
     IM_NOT_AI_DIAGNOSE_CMD='cp {input} {diagnosis}' \
     IM_NOT_AI_REFINE_CMD='cp {input} {output}' \
     .venv/bin/python -m uvicorn app.main:app --port 8000 \
     > "$LOG_DIR/backend.log" 2>&1 < /dev/null &)
  for i in $(seq 1 30); do curl -sf http://localhost:8000/health >/dev/null && break; sleep 1; done
  curl -sf http://localhost:8000/health >/dev/null && echo "[backend] OK" || { echo "[backend] 실패 — $LOG_DIR/backend.log 확인"; exit 1; }
fi

# 2) 프론트 (빠른 ext4 빌드 디렉터리 사용)
if port_up 5173; then
  echo "[frontend] 이미 실행 중 (:5173)"
else
  echo "[frontend] vite 기동..."
  (cd "$BUILD" && setsid nohup npx vite --host --port 5173 --strictPort \
     > "$LOG_DIR/frontend.log" 2>&1 < /dev/null &)
  for i in $(seq 1 40); do port_up 5173 && break; sleep 1; done
  port_up 5173 && echo "[frontend] OK" || { echo "[frontend] 실패 — $LOG_DIR/frontend.log 확인"; exit 1; }
fi

# 3) LM Studio 자동 감지 → 미등록 시 기본 엔드포인트 생성 (로컬 무료, 키 불필요)
if ! port_up 1234; then
  echo "[llm] LM Studio(:1234) 미감지 — S7 설정에서 나중에 등록 가능"
else
  curl -sf http://localhost:8000/api/v1/ai/endpoints 2>/dev/null | grep -q "1234" || {
    # 실제 로드된 모델명을 조회해 default_model로 등록 (스키마 계약 필드: default_model)
    MODEL=$(curl -sf http://localhost:1234/v1/models 2>/dev/null \
      | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['data'][0]['id'] if d.get('data') else '')" 2>/dev/null || true)
    curl -s -X POST http://localhost:8000/api/v1/ai/endpoints -H 'Content-Type: application/json' \
      -d "{\"name\":\"Local LM Studio\",\"base_url\":\"http://localhost:1234/v1\",\"api_key\":\"lm-studio\",\"default_model\":\"${MODEL}\"}" >/dev/null 2>&1 \
      && echo "[llm] LM Studio 엔드포인트 등록 (기본 모델: ${MODEL:-미지정 — S7에서 선택})"
  }
fi

echo "[done] http://localhost:5173"
command -v cmd.exe >/dev/null && cmd.exe /c start "" "http://localhost:5173" 2>/dev/null
