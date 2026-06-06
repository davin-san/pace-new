#!/usr/bin/env python3
"""Verify pace-new and pace-lite consume the same replay schedule."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
PACE_LITE = WORKSPACE / "pace-lite"
OUT = ROOT / "verif" / "out" / "shared_replay"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def traffic(stats: dict[str, object]) -> dict[str, int]:
    raw = stats["traffic"]
    return {
        "injected_packets": int(raw["injected_packets"]),
        "delivered_packets": int(raw["delivered_packets"]),
        "injected_flits": int(raw["injected_flits"]),
        "delivered_flits": int(raw["delivered_flits"]),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    replay = OUT / "deterministic_mesh2x2.replay.json"
    topology = OUT / "pace_new_topology.json"
    pace_new_stats = OUT / "pace_new_stats.json"
    pace_lite_stats = OUT / "pace_lite_stats.json"

    steps = [
        (
            "generate replay",
            [
                sys.executable,
                str(ROOT / "tools" / "generate_replay.py"),
                "--scenario", "deterministic-mesh2x2",
                "--output", str(replay),
            ],
            ROOT,
        ),
        (
            "generate pace-new topology",
            [
                sys.executable,
                str(ROOT / "configs" / "example" / "garnet_synth_traffic.py"),
                "--num-cpus", "4",
                "--num-dirs", "0",
                "--network", "garnet",
                "--topology", "Mesh_XY",
                "--mesh-rows", "2",
                "--sim-cycles", "120",
                "--synthetic", "uniform_random",
                "--injectionrate", "0.0",
                "--num-packets-max", "0",
                "--output", str(topology),
            ],
            ROOT,
        ),
        (
            "build pace-lite",
            ["make", "all"],
            PACE_LITE,
        ),
        (
            "run pace-new replay",
            [
                str(ROOT / "pace-new"),
                "--topology-json", str(topology),
                "--simulate",
                "--replay-json", str(replay),
                "--stats-json", str(pace_new_stats),
            ],
            ROOT,
        ),
        (
            "run pace-lite replay",
            [
                str(PACE_LITE / "pace-lite"),
                "--profile", str(PACE_LITE / "test_profile.json"),
                "--topology", str(PACE_LITE / "mesh2x2.conf"),
                "--output", str(pace_lite_stats),
                "--replay", str(replay),
            ],
            PACE_LITE,
        ),
    ]

    for label, cmd, cwd in steps:
        proc = run(cmd, cwd)
        if proc.returncode != 0:
            print(f"{label}: FAIL")
            print(proc.stdout)
            return proc.returncode

    pace_new = json.loads(pace_new_stats.read_text())
    pace_lite = json.loads(pace_lite_stats.read_text())
    expected = {
        "injected_packets": 6,
        "delivered_packets": 6,
        "injected_flits": 6,
        "delivered_flits": 6,
    }
    new_traffic = traffic(pace_new)
    lite_traffic = traffic(pace_lite)
    if new_traffic != expected:
        print(f"pace-new replay mismatch: {new_traffic} expected {expected}")
        return 1
    if lite_traffic != expected:
        print(f"pace-lite replay mismatch: {lite_traffic} expected {expected}")
        return 1
    if new_traffic != lite_traffic:
        print(f"shared replay mismatch: {new_traffic} != {lite_traffic}")
        return 1

    print("shared_replay: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
