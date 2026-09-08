# AI context baseline probes — before fix

- Time: 2026-09-08T03:44:12.928192+00:00
- Branch/head: `feat/ai-context-consistency` at `70ec67e`
- Scope: read-only runtime baseline for approved AI-context work. No feature code implementation.
- Research starting point: `docs/audits/ai-context-flow-research.md`.
- Native command: `cmd.exe /c "cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe ..\.eval_tmp\ai-context-baseline-probes\probe_ai_context_baseline.py"`
- Exit: `0` in 2.37s.
- Native env was set inside the probe script before `app` import:
  - `DATABASE_URL=sqlite:///<tempfile.gettempdir()>/jippeel_ai_context_probe_*/probe.db`
  - `JIPPEEL_ALLOW_TEMP_CREATE_ALL=1`
- Network control: `app.services.llm.make_client`, `stream_chat`, and `complete_chat` were monkeypatched. No real LLM HTTP client was used.
- Synthetic DB cleanup: `True`.

## Probe A1 — selected character/lore from another project enter generation context

Input used project A chapter plus project B selected character and lore:

```json
{"project_a": 1, "chapter_a": 1, "project_b": 2, "character_b": 1, "lore_b": 1}
```

Observed HTTP `200`, SSE events `['start', 'message', 'done']`. The request was not rejected.

Same intercepted LLM user message contained all of these markers:

```json
{
  "A_SELECTED_CHAPTER_BODY_ONLY": true,
  "B_INTRUDER_CHARACTER_NAME": true,
  "B_INTRUDER_LORE_TITLE": true,
  "B_INTRUDER_LORE_CONTENT": true
}
```

Excerpt:

```text
다음 컨텍스트를 참고해 작성하세요.

[현재 회차: A_SELECTED_CHAPTER_TITLE]
A_SELECTED_CHAPTER_BODY_ONLY

[캐릭터: B_INTRUDER_CHARACTER_NAME]
appearance: B_INTRUDER_APPEARANCE
speech_style: B_INTRUDER_SPEECH

[세계관: B_INTRUDER_LORE_TITLE]
B_INTRUDER_LORE_CONTENT

---

지시:
selected mismat
```

## Probe A2 — explicit project_id B mixes with chapter A

Input used project A chapter, but `context.project_id` pointed at project B. Project B had style profile, auto lore, and installed foreshadow.

```json
{"project_a": 3, "chapter_a": 2, "project_b": 4, "lore_b": 2, "foreshadow_b": 1}
```

Observed HTTP `200`, SSE events `['start', 'message', 'done']`. The request was not rejected.

Runtime observations:

```json
{
  "system_contains_project_b_style": true,
  "user_contains_project_a_chapter": true,
  "user_contains_project_b_auto_lore": true,
  "user_contains_project_b_foreshadow": true,
  "blocked_or_rejected": false
}
```

Excerpt:

```text
다음 컨텍스트를 참고해 작성하세요.

[현재 회차: A_PID_CHAPTER_TITLE]
A_PID_CHAPTER_BODY_ONLY

[세계관(자동): B_AUTO_LORE_TITLE]
B_AUTO_LORE_CONTENT

[미회수 복선: B_FORESHADOW_TITLE]
B_FORESHADOW_CONTENT
→ 이 복선은 아직 회수 전이다. 이 화에서 건드릴 거면 자연스럽게, 건드리지 않으면 결론을 미리 풀지 마라.

---

지시:
B_AUTO
```

## Probe B — selected relationship data is omitted

A relationship row existed for the two selected characters:

```json
{
  "id": 1,
  "from_character_id": 2,
  "to_character_id": 3,
  "label": "BLOOD_OATH_LABEL_777",
  "note": "HIDDEN_REL_NOTE_888"
}
```

Observed HTTP `200`, SSE events `['start', 'message', 'done']`.

The intercepted user message included both selected character names, but not the relationship label/note:

```json
{
  "selected_characters_present": true,
  "relationship_label_present": false,
  "relationship_note_present": false,
  "relationship_block_present": false
}
```

Excerpt for missing relationship markers:

```json
{
  "REL_SOURCE_CHARACTER": "다음 컨텍스트를 참고해 작성하세요.\n\n[현재 회차: REL_CHAPTER_TITLE]\nREL_CHAPTER_BODY_ONLY\n\n[캐릭터: REL_SOURCE_CHARACTER]\nappearance: source appearance\n\n[캐릭터: REL_TARGET_CHARACTER]\nappearance: target appearance\n\n---\n\n지시:\nrelationship omission prompt",
  "REL_TARGET_CHARACTER": "다음 컨텍스트를 참고해 작성하세요.\n\n[현재 회차: REL_CHAPTER_TITLE]\nREL_CHAPTER_BODY_ONLY\n\n[캐릭터: REL_SOURCE_CHARACTER]\nappearance: source appearance\n\n[캐릭터: REL_TARGET_CHARACTER]\nappearance: target appearance\n\n---\n\n지시:\nrelationship omission prompt",
  "BLOOD_OATH_LABEL_777": false,
  "HIDDEN_REL_NOTE_888": false
}
```

## Probe C — style profile reaches single but not parallel phases

Same project/chapter was used with `context.style_profile=true` for both `/ai/generate` and `/ai/generate-parallel`.

Single generation included the style token in the system message:

```json
{
  "single_system_contains_style_token": true
}
```

Parallel generation did not include the style token in planner, workers, or reviewer system/user messages, although each parallel phase did receive the chapter context:

```json
{
  "single_system_contains_style_token": true,
  "parallel_system_style_token_by_phase": {
    "parallel_planner_complete": false,
    "parallel_worker_complete_1": false,
    "parallel_worker_complete_2": false,
    "parallel_reviewer_stream": false
  },
  "parallel_user_style_token_by_phase": {
    "parallel_planner_complete": false,
    "parallel_worker_complete_1": false,
    "parallel_worker_complete_2": false,
    "parallel_reviewer_stream": false
  },
  "parallel_user_chapter_context_by_phase": {
    "parallel_planner_complete": true,
    "parallel_worker_complete_1": true,
    "parallel_worker_complete_2": true,
    "parallel_reviewer_stream": true
  }
}
```

Single system excerpt:

```text
묘사의 연속 금지
- '그러나', '한편' 같은 느린 전환 남발 금지
- 원고 외의 설명·요약·메타 코멘트 금지. 출력은 원고 본문만.

[작품 문체 프로파일 — 반드시 따른다]
STYLE_TOKEN_PROJECT_A — hardboiled terse rhythm
```

## Limits

- These are runtime probes with deterministic intercepted LLM calls. They prove the messages passed to `app.services.llm`, not model behavior.
- The probes use backend `TestClient` and a temporary SQLite DB only. They do not start ports `8000` or `5173`.
- No frontend request-snapshot behavior was exercised here.
- No source behavior was changed.

## Files

- Machine-readable result: `docs/audits/ai-context-baseline-probes.json`
- Probe script and raw stdout: `.eval_tmp/ai-context-baseline-probes/`
