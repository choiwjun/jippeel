# AI context final docs cold read

## Scope

I cold-read only the supplied document contents in the task prompt. I did not open linked files, source files, neighboring docs, tests, or services.

## What the supplied documents are/do/expect

- `ai-context-final-validation` is the current state report. It says the approved AI context consistency work is implemented, independently reviewed, and finally verified, but not deployed. It names the branch, source commit, preservation baseline, verification results, boundary evidence, known limits, and follow-up validation rules.
- `ai-context-consistency` is a runbook for users and reviewers. It explains how episode AI generation, parallel generation, contradiction checks, character/world AI requests, context options, foreshadowing permissions, and save/revision handling should behave. It also gives safe local revalidation commands and operational constraints.
- `ai-context-lessons` is a reusable validation checklist for future changes. It turns past failures into gates around identity, UI option policy, consumed provider input, SPA stale state, async ownership, hash verification, test environment setup, and worker status reporting.
- The handoff note summarizes the current branch status and points readers to the final validation report, runbook, and lessons. It also says older handoff history should remain below it.

## Findings

### 1. Handoff note has a dangling preservation statement in the supplied text

The handoff says: “아래 기존 인계 기록은 보존한다.” The supplied content then ends after a separator. From the supplied text alone, there is no older handoff record below it.

Impact: If this is the complete artifact, the handoff promises preserved history that is not present. If the real file has more content below the supplied excerpt, this is not an issue.

### 2. Revalidation prerequisites are assumed, not checked

The runbook requires an existing Windows `backend/.venv`, frontend dependencies, and Playwright browsers, and says not to install new dependencies. It does not state a preflight command or expected failure mode when these prerequisites are missing.

Impact: A reader can follow the commands and fail for environment readiness reasons without knowing whether the product or the local setup is at fault.

### 3. Port-safety step is clear in intent but incomplete operationally

The runbook says occupied dedicated ports must abort the run, and existing servers must not be stopped or replaced with ports 8000/5173. It does not give the exact port-check command or expected evidence format in the runbook body.

Impact: The safety rule is understandable, but execution is easy to vary between reviewers. That can weaken reproducibility.

### 4. Evidence output locations are split across names

The final validation report names preserved raw evidence under `.eval_tmp/ai-context-final-parent/`. The runbook warns that the default `.eval_tmp/ai-context-task-4/` pointer and `frontend/test-results/` may be overwritten.

Impact: These may be intentionally different locations, but the relationship is not explained in the supplied text. A reader may not know which path is the stable final evidence, which path is a moving pointer, and which path a fresh run should preserve.

### 5. “holding” is not defined

The runbook says Windows Playwright can leave fixture reports in `holding`, and that separate PID/port checks can be used as evidence. The term `holding` is not defined in the supplied text.

Impact: A reader may not know whether `holding` is a status, a directory, a test reporter field, or an artifact label.

### 6. Historical defect notes could be misread as current defects

The final validation report lists S2 and S3 under “최종 지적과 증거의 한계”, then says fixes were made. The top state also says final Spec/Standards found no remaining blockers.

Impact: This is not a direct contradiction, but the heading can make fixed historical findings look like still-open final findings. A label such as “해결된 지적” would reduce ambiguity.

## Blocking issue assessment

No definite blocker is visible from the supplied text. The only potentially blocking issue is the handoff note ending after it says old records are preserved below, if that is the complete handoff file.

## Small optional improvements

- Add a short preflight section for dependency readiness and port checks.
- Explain the relationship between `.eval_tmp/ai-context-final-parent/`, `.eval_tmp/ai-context-task-4/`, and `frontend/test-results/`.
- Define `holding` where it first appears.
- Rename “최종 지적과 증거의 한계” to separate resolved findings from unverified scope limits.
