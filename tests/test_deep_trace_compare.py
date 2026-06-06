#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRIALS = ROOT / "verif" / "trials" / "garnet_deep_trace_matrix.json"
GEM5_OUT = ROOT / "verif" / "out" / "gem5_trace"
PACE_OUT = ROOT / "verif" / "out" / "pace_deep_trace"
CANONICAL_OUT = ROOT / "verif" / "out" / "deep_trace_canonical"


def main() -> int:
    _run([sys.executable, str(ROOT / "tests" / "test_gem5_trace_generation.py")])
    _run([sys.executable, str(ROOT / "tests" / "test_pace_deep_trace_generation.py")])
    for trial in __import__("json").loads(TRIALS.read_text()):
        name = str(trial["name"])
        canonical_dir = CANONICAL_OUT / name
        _run([
            sys.executable,
            str(ROOT / "tools" / "compare_deep_traces.py"),
            str(GEM5_OUT / name / "trace.jsonl"),
            str(PACE_OUT / name / "trace.jsonl"),
            "--canonical-dir",
            str(canonical_dir),
        ])
    print("deep_trace_compare_test: PASS")
    return 0


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(cmd)}\nOUTPUT:\n{proc.stdout}"
        )
    return proc


if __name__ == "__main__":
    raise SystemExit(main())
