#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "configs" / "example" / "garnet_synth_traffic.py"
PACE = ROOT / "pace-new"
OUT = ROOT / "verif" / "out" / "pace"


def main() -> int:
    if not PACE.exists():
        raise RuntimeError("pace-new executable is missing; run make all first")

    _case(
        "mesh2x2",
        [
            "--num-cpus=4",
            "--num-dirs=4",
            "--network=garnet",
            "--topology=Mesh_XY",
            "--mesh-rows=2",
            "--sim-cycles=50",
            "--synthetic=uniform_random",
            "--injectionrate=0.01",
        ],
        "nodes=8 routers=4 ext_links=8 int_links=8",
    )
    _case(
        "hetero3d",
        [
            "--num-cpus=4",
            "--num-dirs=4",
            "--network=garnet",
            "--topology=HeteroChiplet",
            "--chiplet-spec",
            str(ROOT / "configs" / "chiplets" / "example_3d.json"),
            "--sim-cycles=50",
            "--synthetic=uniform_random",
            "--injectionrate=0.01",
        ],
        "nodes=8 routers=12 ext_links=8 int_links=34",
    )

    print("runtime_instantiation: PASS")
    return 0


def _case(name: str, args: list[str], expected: str) -> None:
    case_dir = OUT / name
    case_dir.mkdir(parents=True, exist_ok=True)
    topology_json = case_dir / "topology.json"
    _run([
        sys.executable,
        str(GENERATOR),
        *args,
        "--output",
        str(topology_json),
    ])
    proc = _run([str(PACE), "--topology-json", str(topology_json)])
    if expected not in proc.stdout:
        raise AssertionError(proc.stdout)


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
