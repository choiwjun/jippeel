#!/usr/bin/env python3
"""Deterministic im-not-ai script stub for isolated preservation QA.

The backend humanize wrapper expects two files under IM_NOT_AI_ROOT/scripts:
prepare_monolith_input.py and verify_gates.py. The fixture copies this file to
both names inside a temp IM_NOT_AI_ROOT.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def prepare(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--genre", default="essay")
    parser.add_argument("--diagnosis")
    args = parser.parse_args(argv)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    input_path = run_dir / "01_input.txt"
    text = input_path.read_text(encoding="utf-8", errors="replace") if input_path.exists() else ""
    metrics = {
        "route_hint": "light",
        "genre": args.genre,
        "qa_stub": True,
        "char_count": len(text),
    }
    (run_dir / "00_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False), encoding="utf-8")
    combined = "[QA metrics]\n" + json.dumps(metrics, ensure_ascii=False) + "\n\n[원문]\n" + text
    if args.diagnosis:
        diagnosis = Path(args.diagnosis).read_text(encoding="utf-8", errors="replace")
        combined = "[QA diagnosis]\n" + diagnosis + "\n\n" + combined
    (run_dir / "01_input_with_metrics.txt").write_text(combined, encoding="utf-8")
    return 0


def verify(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--genre", default="essay")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    before = Path(args.before).read_text(encoding="utf-8", errors="replace")
    after = Path(args.after).read_text(encoding="utf-8", errors="replace")
    raw = {
        "qa_stub": True,
        "genre": args.genre,
        "before_chars": len(before),
        "after_chars": len(after),
        "change_rate": {"rate": 0.01},
        "gates": [],
    }
    print(json.dumps(raw, ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    script_name = Path(sys.argv[0]).name
    if script_name == "verify_gates.py" or "--before" in argv:
        return verify(argv)
    return prepare(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
