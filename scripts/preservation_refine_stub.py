#!/usr/bin/env python3
"""Deterministic im-not-ai command stub for manuscript-preservation QA.

This script is used only by scripts/preservation_backend_fixture.py through the
backend's IM_NOT_AI_DIAGNOSE_CMD and IM_NOT_AI_REFINE_CMD environment variables.
It never calls external models.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def clean_path(value: str) -> Path:
    # app.services.humanize uses POSIX shlex.quote before shell=True. On Windows
    # cmd.exe treats single quotes as literal characters, so strip them here.
    return Path(value.strip("'\""))


def append_log(mode: str, input_path: Path, output_path: Path) -> None:
    log = os.environ.get("JIPPEEL_PRESERVATION_STUB_LOG")
    if not log:
        return
    entry = {"mode": mode, "input": str(input_path), "output": str(output_path)}
    path = Path(log)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in {"diagnose", "refine"}:
        print("usage: preservation_refine_stub.py diagnose|refine INPUT OUTPUT", file=sys.stderr)
        return 2
    mode = argv[1]
    input_path = clean_path(argv[2])
    output_path = clean_path(argv[3])
    text = input_path.read_text(encoding="utf-8", errors="replace") if input_path.exists() else ""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "diagnose":
        output_path.write_text(
            "# QA deterministic diagnosis\n\n- A-1 [S3] 합성 원고 점검: \"첫 문장입니다\"\n",
            encoding="utf-8",
        )
    else:
        # Preserve the input visibly and add a small marker. The companion gate
        # stub returns a low change ratio so this remains acceptable.
        body = text.split("[원문]", 1)[-1].strip() if "[원문]" in text else text.strip()
        output_path.write_text(body + "\n\n[QA 윤문 stub]", encoding="utf-8")
    append_log(mode, input_path, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
