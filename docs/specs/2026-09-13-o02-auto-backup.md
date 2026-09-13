# O02 — 자동 주기 백업 (얇은 슬라이스)

승인: 사용자 전체 위임. 범위: opt-in 스케줄러 + 보존 프루닝 + 테스트.
비목표: 클라우드 동기화·Git 버전 관리·삭제 복구 UI(외부 의존·별도 승인 필요).

## 설계

### `app/services/auto_backup.py`

- `AutoBackupConfig.from_env()` — 모두 선택적:
  - `JIPPEEL_AUTOBACKUP_INTERVAL_MIN` — 분 단위. 미설정·0·음수면 `enabled=False`.
  - `JIPPEEL_AUTOBACKUP_DIR` — 기본 `~/.jippeel/backups/auto`.
  - `JIPPEEL_AUTOBACKUP_KEEP` — 보존 개수, 기본 5, 최소 1.
- `run_backup_once(cfg, source_db, now=None) -> Path` —
  `<base>/<UTC %Y%m%d-%H%M%S[-n]>/`에 `create_backup` 호출 후 프루닝, manifest 경로 반환.
  동일 초 충돌은 `-1`, `-2` 접미사로 회피.
- `prune_backups(cfg)` — 타임스탬프 패턴 디렉터리만 최신 `keep`개 남기고 삭제.
  패턴 불일치·비어있지 않은 비백업 이름은 건드리지 않는다(삭제는 `shutil.rmtree`,
  대상은 base 디렉터리 직계 자식 중 이름 패턴 일치분만).
- `start_scheduler(cfg, source_db) -> Callable[[], None]` —
  daemon thread + `threading.Event` 루프. `interval_min`마다 `run_backup_once`.
  각 반복의 예외는 잡아 경고 로그만 남기고 스케줄러를 죽이지 않는다(non-blocking).
  반환된 stop 함수로 종료 대기.

### 수명주기 연결 (`main.py`)

`lifespan`에서 `AutoBackupConfig.from_env().enabled`면 스케줄러 시작,
`yield` 이후 stop 호출. 기본 미설정이면 아무것도 하지 않음 — 테스트 격리 무영향.

## 검증

- config 파스(기본값·잘못된 값·비활성).
- `run_backup_once`: 실제 임시 jippeel DB(alembic_version 포함) 대상 백업 생성·manifest.
- 타임스탬프 충돌 접미사.
- 프루닝: keep 초과분만 삭제·패턴 외 디렉터리 보존.
- 스케줄러: fake interval로 1회 이상 tick 후 stop(대기 시간 최소).
- 반복 중 백업 실패가 스케줄러를 죽이지 않음.
