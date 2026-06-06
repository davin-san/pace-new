#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "configs" / "example" / "garnet_synth_traffic.py"
PACE = ROOT / "pace-new"
OUT = ROOT / "verif" / "out" / "pace" / "trace_generation"


def main() -> int:
    if not PACE.exists():
        raise RuntimeError("pace-new executable is missing; run make all first")

    OUT.mkdir(parents=True, exist_ok=True)
    topology_json = OUT / "topology.json"
    stats_json = OUT / "stats.json"
    trace_jsonl = OUT / "trace.jsonl"

    _run([
        sys.executable,
        str(GENERATOR),
        "--num-cpus=4",
        "--num-dirs=4",
        "--network=garnet",
        "--topology=Mesh_XY",
        "--mesh-rows=2",
        "--sim-cycles=20",
        "--synthetic=uniform_random",
        "--injectionrate=1.0",
        "--inj-vnet=0",
        "--num-packets-max=1",
        "--single-sender-id=0",
        "--single-dest-id=3",
        "--seed=1",
        "--output",
        str(topology_json),
    ])
    _run([
        str(PACE),
        "--topology-json",
        str(topology_json),
        "--simulate",
        "--drain-cycles",
        "120",
        "--stats-json",
        str(stats_json),
        "--trace-jsonl",
        str(trace_jsonl),
    ])

    events = [json.loads(line) for line in trace_jsonl.read_text().splitlines()]
    names = {event["event"] for event in events}
    required = {
        "simulation.trace_enabled",
        "runtime.network_config",
        "runtime.router",
        "runtime.network_interface",
        "runtime.ext_link",
        "runtime.int_link",
        "runtime.instantiated",
        "topology.ext_link",
        "topology.int_link",
        "topology.make_link",
        "message_buffer.enqueue",
        "message_buffer.dequeue",
        "event.schedule",
        "event.wakeup",
        "traffic.inject_attempt",
        "traffic.inject",
        "traffic.deliver",
        "simulation.complete",
    }
    missing = required - names
    if missing:
        raise AssertionError(f"missing trace events: {sorted(missing)}")

    injects = [event for event in events if event["event"] == "traffic.inject"]
    deliveries = [event for event in events if event["event"] == "traffic.deliver"]
    if len(injects) != 1 or len(deliveries) != 1:
        raise AssertionError(
            f"expected one injected and delivered packet, got "
            f"{len(injects)} injected and {len(deliveries)} delivered"
        )
    injected = injects[0]
    delivered = deliveries[0]
    if injected["source"] != 0 or injected["dest_node"] != 7:
        raise AssertionError(injected)
    if delivered["node"] != 7 or delivered["vnet"] != 0:
        raise AssertionError(delivered)

    print("trace_generation: PASS")
    return 0


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
