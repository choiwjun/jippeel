# O01 — SillyTavern 카드 PNG import/export + novelWriter import (얇은 슬라이스)

승인 상태: 사용자 전체 위임("나대신 승인하고 남은거 다 작업해")에 따라 실행.
범위: 서비스 계층 + HTTP 엔드포인트 + 테스트. UI·외부 연동 없음. stdlib 전용(신규 의존성 없음).

## 1. 카드 PNG (SillyTavern V2)

`Character.card_json`의 주석("ST 호환 확장 여지")을 실체화한다.

### 서비스 `app/services/card_png.py`

- `character_to_card(character) -> dict` — Character → SillyTavern V2 카드
  `{"spec":"chara_card_v2","spec_version":"2.0","data":{...}}`.
  `data` 매핑: `name`←name, `description`←background+appearance 병합, `personality`←personality,
  `first_mes`/`mes_example`←card_json 내 ST 키(있으면), `character_book` 등 기타 card_json 키는 통과.
- `build_card_png(card: dict) -> bytes` — 1×1 RGBA PNG(고정 픽셀)에 `tEXt` 청크
  `chara`=base64(utf8 JSON) 삽입. CRC 포함.
- `parse_card_png(data: bytes) -> dict` — PNG 시그니처·청크 순회, `tEXt`/`iTXt`에서
  `chara` 키워드 탐색 → base64 → JSON. 카드 미존재·손상·비JSON이면 `ValueError`.
- `card_to_character_fields(card: dict) -> dict` — 카드 → Character 필드
  (`name`, `personality`, `background`←description, `card_json`←전체 카드 보존).
  `data` 래퍼와 평면 카드 둘 다 허용.

### 엔드포인트

- `GET /characters/{chid}/card.png` → `image/png` + `Content-Disposition: attachment`.
- `POST /projects/{pid}/characters/import-card` (multipart `file`) → 카드 파스 →
  Character 생성 → `CharacterOut` 201. 파스 실패 422, 비PNG/미카드 422.

## 2. novelWriter import

novelWriter 프로젝트 = 루트 `.nwx`(XML) + `content/<handle>.nws` 문서.
zip 업로드만 허용(단일 .nwx만 있으면 content가 없어 빈 프로젝트 → 422로도 충분).

### 서비스 `app/services/novelwriter_import.py`

- `parse_project_zip(zip_bytes) -> NovelWriterImport(name, chapters)`
  - `.nwx` XML 파스: `<content>`의 `<item>`을 `order` 속성 순으로 정렬.
  - `type="FILE"` + `layout="DOCUMENT"`인 항목만 챕터 후보. `type="FILE"`만 있고
    layout 없는 구형도 허용.
  - 각 항목의 `content/<handle>.nws`를 읽어 `%%~` 메타 헤더를 건너뛰고 본문 추출.
  - 제목: 본문 첫 `#`-계열 헤딩, 없으면 item `<name>`.
  - 후보 0개면 `ValueError`.
- 챕터는 순서대로 `sort_order` 0,1,2…로 생성, `status="초고"`.

### 엔드포인트

- `POST /projects/{pid}/import/novelwriter` (multipart `file`, .zip) →
  `{"project_name": str, "created": int, "chapter_ids": [int]}` 201.
  zip 손상·nwx 부재·문서 0개 → 422.

## 3. 비목표

- PNG에 커스텀 픽셀/썸네일 렌더링(고정 1×1로 충분 — 카드 데이터가 목적).
- novelWriter notes/characters 임포트(NOVEL 문서만), Git/cloud 동기화, UI.

## 4. 검증

- 서비스 단위: PNG 왕복·손상/비카드/빈 데이터, nwx 파스 순서·필터·제목 폴백.
- API: export 200+재파스 왕복, import-card 201+필드 매핑, novelwriter 201+순서·개수,
  실패 422군.
