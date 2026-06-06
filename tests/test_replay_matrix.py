#!/usr/bin/env python3
"""Replay matrix validator for pace-new.

The replay file is the source of truth. This test checks both final stats and
canonical replay trace events without modifying byte-identical Garnet sources.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verif" / "out" / "replay_matrix"

SCENARIOS_BY_TIER = {
    "quick": [
        "deterministic-mesh2x2",
    ],
    "standard": [
        "deterministic-mesh2x2",
        "mesh4x4-long-paths",
        "mesh4x4-contention",
        "multi-vnet",
        "multi-flit",
        "burst-injection",
        "drain-edge-cases",
    ],
    "stress": [
        "deterministic-mesh2x2",
        "mesh4x4-long-paths",
        "mesh4x4-contention",
        "multi-vnet",
        "multi-flit",
        "burst-injection",
        "drain-edge-cases",
        "mesh8x8-smoke",
        "mesh4x4-multiflit-vnet0",
    ],
}


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def generate_replay(name: str, path: Path) -> dict[str, object]:
    proc = run([
        sys.executable,
        str(ROOT / "tools" / "generate_replay.py"),
        "--scenario", name,
        "--output", str(path),
    ], ROOT)
    if proc.returncode != 0:
        raise AssertionError(proc.stdout)
    return json.loads(path.read_text())


def generate_topology(replay: dict[str, object], path: Path) -> None:
    proc = run([
        sys.executable,
        str(ROOT / "configs" / "example" / "garnet_synth_traffic.py"),
        "--num-cpus", str(int(replay["nodes"])),
        "--num-dirs", "0",
        "--network", "garnet",
        "--topology", "Mesh_XY",
        "--mesh-rows", str(int(replay["mesh_rows"])),
        "--sim-cycles", str(int(replay["sim_cycles"])),
        "--synthetic", "uniform_random",
        "--injectionrate", "0.0",
        "--num-packets-max", "0",
        "--output", str(path),
    ], ROOT)
    if proc.returncode != 0:
        raise AssertionError(proc.stdout)


def run_replay(topology: Path, replay: Path, stats: Path, trace: Path) -> None:
    proc = run([
        str(ROOT / "pace-new"),
        "--topology-json", str(topology),
        "--simulate",
        "--replay-json", str(replay),
        "--stats-json", str(stats),
        "--trace-jsonl", str(trace),
    ], ROOT)
    if proc.returncode != 0:
        raise AssertionError(proc.stdout)


def nonzero_map(values: Counter[int]) -> dict[str, int]:
    return {str(key): value for key, value in sorted(values.items()) if value}


def validate_stats(replay: dict[str, object], stats: dict[str, object]) -> None:
    packets = replay["packets"]
    packet_count = len(packets)
    flit_count = sum(int(packet["flits"]) for packet in packets)
    by_vnet = Counter(int(packet["vnet"]) for packet in packets)
    flits_by_vnet = Counter()
    for packet in packets:
        flits_by_vnet[int(packet["vnet"])] += int(packet["flits"])

    traffic = stats["traffic"]
    expected_cycles = int(replay["sim_cycles"]) + int(replay["drain_cycles"])
    expected = {
        "attempted_packets": packet_count,
        "injected_packets": packet_count,
        "delivered_packets": packet_count,
        "injected_flits": flit_count,
        "delivered_flits": flit_count,
        "injected_by_vnet": nonzero_map(by_vnet),
        "delivered_by_vnet": nonzero_map(by_vnet),
        "injected_flits_by_vnet": nonzero_map(flits_by_vnet),
        "delivered_flits_by_vnet": nonzero_map(flits_by_vnet),
    }
    if int(stats["cycles"]) != expected_cycles:
        raise AssertionError(
            f"cycles {stats['cycles']} != expected {expected_cycles}")
    for key, expected_value in expected.items():
        actual = traffic[key]
        if actual != expected_value:
            raise AssertionError(f"{key}: {actual} != {expected_value}")
    if int(stats["garnet"]["total_link_utilization"]) <= 0:
        raise AssertionError("expected positive link utilization")


def event_key(event: dict[str, object]) -> tuple[int, int, int, int]:
    return (
        int(event["node"]),
        int(event["vnet"]),
        int(event["message_size"]),
        int(event["flits"]),
    )


def packet_delivery_key(packet: dict[str, object]) -> tuple[int, int, int, int]:
    return (
        int(packet["destination"]),
        int(packet["vnet"]),
        int(packet["message_size"]),
        int(packet["flits"]),
    )


def validate_trace(replay: dict[str, object], trace: Path) -> None:
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    injects = [event for event in events if event["event"] == "replay.inject"]
    delivers = [event for event in events if event["event"] == "replay.deliver"]

    packets = sorted(
        replay["packets"],
        key=lambda packet: int(packet["cycle"]),
    )
    if len(injects) != len(packets):
        raise AssertionError(f"injections {len(injects)} != packets {len(packets)}")
    if len(delivers) != len(packets):
        raise AssertionError(f"deliveries {len(delivers)} != packets {len(packets)}")

    for event, packet in zip(injects, packets):
        expected = {
            "tick": int(packet["cycle"]),
            "source": int(packet["source"]),
            "destination": int(packet["destination"]),
            "vnet": int(packet["vnet"]),
            "message_size": int(packet["message_size"]),
            "flits": int(packet["flits"]),
        }
        actual = {key: int(event[key]) for key in expected}
        if actual != expected:
            raise AssertionError(f"inject trace mismatch: {actual} != {expected}")

    expected_deliveries = Counter(packet_delivery_key(packet) for packet in packets)
    actual_deliveries = Counter(event_key(event) for event in delivers)
    if actual_deliveries != expected_deliveries:
        raise AssertionError(
            f"delivery trace mismatch: {actual_deliveries} != "
            f"{expected_deliveries}")

    total_cycles = int(replay["sim_cycles"]) + int(replay["drain_cycles"])
    for event in delivers:
        tick = int(event["tick"])
        if tick < 0 or tick >= total_cycles:
            raise AssertionError(f"delivery tick out of replay window: {tick}")


def validate_scenario(name: str) -> None:
    scenario_out = OUT / name
    scenario_out.mkdir(parents=True, exist_ok=True)
    replay_path = scenario_out / "replay.json"
    topology_path = scenario_out / "topology.json"
    stats_path = scenario_out / "stats.json"
    trace_path = scenario_out / "trace.jsonl"

    replay = generate_replay(name, replay_path)
    generate_topology(replay, topology_path)
    run_replay(topology_path, replay_path, stats_path, trace_path)
    validate_stats(replay, json.loads(stats_path.read_text()))
    validate_trace(replay, trace_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tier",
        choices=sorted(SCENARIOS_BY_TIER),
        default="standard",
    )
    args = parser.parse_args()

    for scenario in SCENARIOS_BY_TIER[args.tier]:
        validate_scenario(scenario)
        print(f"  PASS {scenario}")
    print(f"replay_matrix: PASS tier={args.tier}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
