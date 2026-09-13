#!/usr/bin/env bash
# V01 — 전체 fixture 스위트를 PW_COVERAGE=1로 실행하고 istanbul 산출물을 만든다.
set -u
cd "$(dirname "$0")/.."

CONFIGS=(
  playwright.chapter-goal.config.ts
  playwright.chapter-flow.config.ts
  playwright.preservation.config.ts
  playwright.ai-context.fixture.config.ts
  playwright.memory.config.ts
  playwright.serial-state.config.ts
  playwright.evidence-links.config.ts
  playwright.foreshadow-disposition.config.ts
  playwright.final-edition.config.ts
  playwright.ending-impact.config.ts
  playwright.quality.config.ts
)

rm -rf coverage-raw coverage-final.json coverage-summary.json
export PW_COVERAGE=1
fail=0
for cfg in "${CONFIGS[@]}"; do
  echo "=== $cfg ==="
  if ! npx playwright test --config "$cfg"; then
    echo "FAILED: $cfg"
    fail=1
  fi
done

node scripts/coverage-report.mjs || fail=1
exit $fail
