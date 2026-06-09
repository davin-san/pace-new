#!/usr/bin/env python3
"""Run the current pace-new conformance gates."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def run(label: str, cmd: list[str]) -> bool:
    print(f"== {label} ==")
    proc = subprocess.run(cmd)
    ok = proc.returncode == 0
    print(f"{label}: {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-gem5", action="store_true")
    parser.add_argument(
        "--tier",
        choices=["quick", "standard", "full", "stress"],
        default="standard",
        help=(
            "quick runs fast structural/replay smoke checks; standard adds "
            "the replay matrix; full adds gem5-backed trace comparison; "
            "stress adds larger replay scenarios."
        ),
    )
    parser.add_argument(
        "--with-gem5-trace",
        action="store_true",
        help="Run the gem5 trace-build smoke test. Requires patched gem5 source.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]

    checks = [
        (
            "byte_identity",
            [
                sys.executable,
                str(root / "tools" / "check_garnet_identity.py"),
                "--gem5-garnet",
                str(root.parent / "gem5-25.1" / "src" / "mem" / "ruby" / "network" / "garnet"),
                "--pace-garnet",
                str(root / "src"),
            ],
        ),
        (
            "topology_generation",
            [sys.executable, str(root / "tests" / "test_topology_generation.py")],
        ),
        (
            "runtime_instantiation",
            [sys.executable, str(root / "tests" / "test_runtime_instantiation.py")],
        ),
        (
            "event_queue",
            [sys.executable, str(root / "tests" / "test_event_queue.py")],
        ),
        (
            "packet_movement",
            [sys.executable, str(root / "tests" / "test_packet_movement.py")],
        ),
        (
            "profile_width",
            [sys.executable, str(root / "tests" / "test_profile_width.py")],
        ),
        (
            "trace_generation",
            [sys.executable, str(root / "tests" / "test_trace_generation.py")],
        ),
        (
            "shared_replay",
            [sys.executable, str(root / "tests" / "test_shared_replay.py")],
        ),
    ]

    if args.tier in ("standard", "full", "stress"):
        replay_tier = "stress" if args.tier == "stress" else "standard"
        checks.append((
            "topology_matrix",
            [sys.executable, str(root / "tests" / "test_topology_matrix.py")],
        ))
        checks.append((
            "replay_matrix",
            [
                sys.executable,
                str(root / "tests" / "test_replay_matrix.py"),
                "--tier",
                replay_tier,
            ],
        ))

    checks.append((
        "pace_synth_smoke",
        [sys.executable, str(root / "tools" / "run_pace_synth.py")],
    ))

    run_gem5_trace = (
        args.with_gem5_trace or args.tier in ("full", "stress"))
    if not args.skip_gem5:
        checks.append((
            "gem5_synth_smoke",
            [sys.executable, str(root / "tools" / "run_gem5_synth.py")],
        ))
    if run_gem5_trace and not args.skip_gem5:
        checks.append((
            "gem5_trace_generation",
            [sys.executable, str(root / "tests" / "test_gem5_trace_generation.py")],
        ))
        checks.append((
            "deep_trace_compare",
            [sys.executable, str(root / "tests" / "test_deep_trace_compare.py")],
        ))

    ok = True
    for label, cmd in checks:
        ok = run(label, cmd) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
