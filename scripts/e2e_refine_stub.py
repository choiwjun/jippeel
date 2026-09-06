"""E2E용 윤문 파이프라인 스텁 — IM_NOT_AI_DIAGNOSE_CMD/REFINE_CMD 대상.

humanize._run_external은 shlex.quote로 감싼 경로를 cmd.exe(shell=True)에 넘기므로
인자의 인용부호('...')가 그대로 도착한다 → strip("'\"") 후 사용.

사용법(환경변수 템플릿 예):
  IM_NOT_AI_DIAGNOSE_CMD=python <이파일> diagnose {input} {diagnosis}
  IM_NOT_AI_REFINE_CMD=python <이파일> refine {input} {output}
"""
import sys
from pathlib import Path

DIAGNOSIS_MD = """# 진단 리포트 (E2E stub)

## A. 번역투
- **A-1** [S2] "~에 대하여" 남발 — 시그니처: "테스트응답"
"""


def main() -> int:
    mode, raw_args = sys.argv[1], [a.strip("'\"") for a in sys.argv[2:]]
    src, dst = Path(raw_args[0]), Path(raw_args[1])

    if mode == "diagnose":
        dst.write_text(DIAGNOSIS_MD, encoding="utf-8")
        return 0

    if mode == "refine":
        # 게이트는 run_dir의 원본(01_input.txt)과 final.md를 비교한다.
        # {input}은 메트릭 결합본이므로 형제 파일에서 원문을 읽는다.
        original = (src.parent / "01_input.txt").read_text(encoding="utf-8")
        refined = original.replace("\n\n", "\n")  # 소폭 변경만 — pass 구간 유지
        summary = ("<!-- HUMANIZE-SUMMARY -->\n| 항목 | 값 |\n|---|---|\n"
                   "| 변경률 | 3% |\n<!-- /HUMANIZE-SUMMARY -->")
        dst.write_text(refined + "\n" + summary, encoding="utf-8")
        return 0

    print(f"unknown mode: {mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
