# O03 — 집필 활동 캘린더/통계 (얇은 슬라이스)

승인: 사용자 전체 위임. 범위: 조회 엔드포인트 + 테스트.
비목표: 플랫폼 직접 발행(정책 확인 전 보류 유지)·전용 캘린더 UI(데이터 표면만 제공).

## 설계

멀티 작품 통계는 `GET /projects`의 `chapter_count`/`total_chars`가 이미 제공하므로,
잔여 가치는 **일별 집필 활동**이다.

### `GET /projects/{pid}/writing-activity?days=N`

- `days`: 1~365, 기본 90. 범위 밖은 422.
- 회차 `updated_at`을 `date()`로 버킷팅해 최근 N일 활동을 반환한다.
  `created_at`과 `updated_at` 둘 다가 아니라 **updated_at 단일 기준** — 얇은 슬라이스의
  단순 계약(수정·작성 활동이 같은 축).
- 응답:
  ```json
  {
    "project_id": 1,
    "days": 90,
    "buckets": [{"date": "2026-09-13", "chapters": 2, "chars": 5123}],
    "totals": {"active_days": 1, "chapters": 2, "chars": 5123}
  }
  ```
- `chars`는 해당 일에 업데이트된 회차의 `word_count_cache` 합(현재 길이 스냅샷 —
  일별 델타가 아님을 명시).

## 검증

- 버킷 날짜 그룹·개수·chars 합계.
- 활동 없는 프로젝트 → 빈 buckets, totals 0.
- days 경계값(0·366 → 422), 다른 프로젝트 격리.
