"""V03 — 다중 OS 프로세스 SQLite 동시 쓰기 부하 검증.

앱의 표준 pragma(journal_mode=WAL, synchronous=NORMAL, busy_timeout=5000,
foreign_keys=ON)와 동일한 설정으로 N개의 독립 프로세스가 같은 DB 파일에
BEGIN IMMEDIATE 쓰기 트랜잭션을 반복 커밋한다.

검증 주장:
  - 모든 커밋이 손실 없이 반영된다 (rows == workers * writes).
  - 잠금 경합은 busy_timeout 대기 후 성공하거나 명시적 재시도로 해소된다.
  - 부하 후 PRAGMA integrity_check가 ok를 반환한다.

pytest 격리 대상이 아닌 독립 검증 스크립트 — TEMP 경로의 합성 DB만 사용한다.
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import sqlite3
import sys
import tempfile
import time

PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA foreign_keys=ON",
)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    for stmt in PRAGMAS:
        conn.execute(stmt)


def _worker(db_path: str, worker_id: int, writes: int, queue: mp.Queue) -> None:
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    _apply_pragmas(conn)
    committed = 0
    busy_retries = 0
    max_commit_ms = 0.0
    for seq in range(writes):
        while True:
            start = time.monotonic()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT INTO mp_probe(worker, seq, payload) VALUES (?, ?, ?)",
                    (worker_id, seq, "x" * 64),
                )
                conn.execute("COMMIT")
            except sqlite3.OperationalError as exc:
                conn.execute("ROLLBACK") if conn.in_transaction else None
                if "locked" in str(exc).lower():
                    busy_retries += 1
                    continue
                raise
            elapsed = (time.monotonic() - start) * 1000
            max_commit_ms = max(max_commit_ms, elapsed)
            committed += 1
            break
    conn.close()
    queue.put((worker_id, committed, busy_retries, max_commit_ms))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--writes", type=int, default=50)
    args = parser.parse_args()

    tmpdir = tempfile.mkdtemp(prefix="jippeel-v03-")
    db_path = os.path.join(tmpdir, "mp.db")

    setup = sqlite3.connect(db_path)
    _apply_pragmas(setup)
    setup.execute(
        "CREATE TABLE mp_probe("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "worker INTEGER NOT NULL, seq INTEGER NOT NULL, payload TEXT NOT NULL)"
    )
    setup.commit()
    setup.close()

    queue: mp.Queue = mp.Queue()
    ctx = mp.get_context("spawn")
    procs = [
        ctx.Process(target=_worker, args=(db_path, wid, args.writes, queue))
        for wid in range(args.workers)
    ]
    started = time.monotonic()
    for proc in procs:
        proc.start()
    results = [queue.get() for _ in procs]
    for proc in procs:
        proc.join(timeout=60)
        assert proc.exitcode == 0, f"worker exited {proc.exitcode}"
    wall_s = time.monotonic() - started

    total_committed = sum(r[1] for r in results)
    total_busy = sum(r[2] for r in results)
    worst_commit_ms = max(r[3] for r in results)

    check = sqlite3.connect(db_path)
    rows = check.execute("SELECT COUNT(*) FROM mp_probe").fetchone()[0]
    distinct_workers = check.execute(
        "SELECT COUNT(DISTINCT worker) FROM mp_probe"
    ).fetchone()[0]
    integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
    journal = check.execute("PRAGMA journal_mode").fetchone()[0]
    check.close()

    expected = args.workers * args.writes
    failures = []
    if rows != expected or total_committed != expected:
        failures.append(f"rows {rows}/{expected} committed {total_committed}")
    if distinct_workers != args.workers:
        failures.append(f"distinct workers {distinct_workers}/{args.workers}")
    if integrity != "ok":
        failures.append(f"integrity_check={integrity}")
    if journal != "wal":
        failures.append(f"journal_mode={journal}")

    print(
        f"V03 workers={args.workers} writes/worker={args.writes} "
        f"rows={rows} busy_retries={total_busy} "
        f"max_commit_ms={worst_commit_ms:.1f} wall_s={wall_s:.2f} "
        f"integrity={integrity} journal={journal}"
    )
    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
