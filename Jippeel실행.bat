@echo off
rem Jippeel 대시보드 원클릭 실행 (Windows -> WSL)
rem 운영 모드(A-040): uvicorn 단일 프로세스(:8000)가 API + 프론트(frontend/dist)를 함께 서빙.
rem 개발 모드(백엔드+Vite 핫리로드)는 scripts/dev.sh 를 사용.
wsl.exe -e bash -lc "/mnt/c/Users/wj941/OneDrive/바탕 화면/WJproject/jippeel/scripts/prod.sh"
