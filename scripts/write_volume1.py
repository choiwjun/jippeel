"""1권 집필 러너 — 각 회차를 AI로 생성해 초안으로 저장하는 사용자 요청 도구.

앱 원칙(P1: AI 자동 삽입 금지)은 유지되며, 이 스크립트는 작성자가 명시적으로
요청했을 때 초안을 일괄 생성해 두는 배치 도구다. 저장된 본문은 초고(status=초고)로
에디터에서 검수·수정하는 것을 전제로 한다.

사용: python write_volume1.py <project_id> [endpoint_id]
"""
import json
import sys
import time

import httpx

API = "http://localhost:8000/api/v1"


def get(client, path):
    r = client.get(API + path, timeout=30)
    r.raise_for_status()
    return r.json()


def put_content(client, chapter_id, text):
    r = client.put(f"{API}/chapters/{chapter_id}/content",
                   json={"content_md": text}, timeout=60)
    r.raise_for_status()
    return r.json()


def stream_generate(client, body):
    text = ""
    with client.stream("POST", f"{API}/ai/generate", json=body,
                       timeout=httpx.Timeout(connect=15, read=900, write=15, pool=15)) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            if "delta" in payload:
                text += payload["delta"]
            if "detail" in payload and payload.get("detail"):
                raise RuntimeError(f"SSE 오류: {payload['detail']}")
    return text


def main():
    pid = int(sys.argv[1])
    endpoint_id = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    with httpx.Client() as client:
        chapters = sorted(get(client, f"/projects/{pid}/chapters"),
                          key=lambda c: (c["volume"], c["sort_order"]))
        characters = get(client, f"/projects/{pid}/characters")
        char_ids = [c["id"] for c in characters]
        print(f"프로젝트 {pid} — 회차 {len(chapters)}개 · 캐릭터 {len(characters)}명", flush=True)

        for i, ch in enumerate(chapters):
            detail = get(client, f"/chapters/{ch['id']}")
            if detail.get("content_md", "").strip() and "--force" not in sys.argv:
                wc = detail.get("word_count_cache", 0)
                print(f"[{i + 1}/{len(chapters)}] {ch['title']} — 이미 본문 있음({wc:,}자), 건너뜀", flush=True)
                continue
            memo = detail.get("memo") or "(목차 정보 없음 — 로그라인에 맞춰 자유 집필)"
            prompt = (
                f"이번 화({ch['title']}) 본문을 집필하라.\n\n[이번 화 목차]\n{memo}\n\n"
                "요구사항:\n"
                "- 공백 포함 4,500~5,500자 분량으로 쓸 것\n"
                "- 목차의 시놉시스와 핵심 사건을 반드시 포함할 것\n"
                "- 장면 묘사와 대사 중심으로 전개하고, 마지막 문장은 다음 화로 넘어가는 훅으로 끝낼 것"
            )
            if i > 0:
                prompt += "\n- 직전 회차 끝부분에서 자연스럽게 이어서 시작할 것"
            body = {
                "endpoint_id": endpoint_id,
                "prompt_override": prompt,
                "context": {
                    "chapter_id": ch["id"],
                    "character_ids": char_ids,
                    "auto_lore": True,
                    "previous_chapter": i > 0,
                },
                "params": {"max_tokens": 6500},
            }
            t0 = time.time()
            print(f"[{i + 1}/{len(chapters)}] {ch['title']} 생성 중…", flush=True)
            try:
                text = stream_generate(client, body)
            except Exception as exc:  # noqa: BLE001 — 한 화 실패가 전체를 멈추지 않게
                print(f"  ✗ 실패({time.time() - t0:.0f}초): {exc}", flush=True)
                continue
            saved = put_content(client, ch["id"], text)
            print(f"  ✓ 저장: {len(text):,}자 (노벨피아 {saved['word_count_cache']:,}) "
                  f"— {time.time() - t0:.0f}초", flush=True)

        print("완료", flush=True)


if __name__ == "__main__":
    main()
