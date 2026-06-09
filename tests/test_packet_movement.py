#!/usr/bin/env python3
from __future__ import annotations

import re
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "configs" / "example" / "garnet_synth_traffic.py"
PACE = ROOT / "pace-new"
OUT = ROOT / "verif" / "out" / "pace" / "packet_movement"


def main() -> int:
    if not PACE.exists():
        raise RuntimeError("pace-new executable is missing; run make all first")

    _case("vnet0_control", 0)
    _case("vnet1_data", 1)

    print("packet_movement: PASS")
    return 0


def _case(name: str, vnet: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    topology_json = OUT / f"{name}.json"
    _run([
        sys.executable,
        str(GENERATOR),
        "--num-cpus=4",
        "--num-dirs=4",
        "--network=garnet",
        "--topology=Mesh_XY",
        "--mesh-rows=2",
        "--sim-cycles=40",
        "--synthetic=uniform_random",
        "--injectionrate=1.0",
        f"--inj-vnet={vnet}",
        "--num-packets-max=2",
        "--single-sender-id=0",
        "--single-dest-id=3",
        "--seed=1",
        "--output",
        str(topology_json),
    ])
    proc = _run([
        str(PACE),
        "--topology-json",
        str(topology_json),
        "--simulate",
        "--drain-cycles",
        "120",
        "--stats-json",
        str(OUT / f"{name}_stats.json"),
    ])
    injected = _metric(proc.stdout, "injected")
    delivered = _metric(proc.stdout, "delivered")
    if injected != 2 or delivered != 2:
        raise AssertionError(proc.stdout)
    stats = json.loads((OUT / f"{name}_stats.json").read_text())
    traffic = stats["traffic"]
    if traffic["injected_packets"] != 2:
        raise AssertionError(stats)
    if traffic["delivered_packets"] != 2:
        raise AssertionError(stats)
    expected_flits = 10 if vnet == 1 else 2
    if traffic["injected_flits"] != expected_flits:
        raise AssertionError(stats)
    if traffic["delivered_flits"] != expected_flits:
        raise AssertionError(stats)
    if stats["garnet"]["total_link_utilization"] <= 0:
        raise AssertionError(stats)


def _metric(text: str, key: str) -> int:
    match = re.search(rf"{key}=([0-9]+)", text)
    if not match:
        raise AssertionError(text)
    return int(match.group(1))


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )
    return proc


if __name__ == "__main__":
    raise SystemExit(main())
