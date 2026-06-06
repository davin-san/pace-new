#!/usr/bin/env python3
"""Generate deterministic packet replay schedules shared by validators."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


NI_FLIT_SIZE = 16
VNETS = 3


def packet(cycle: int, source: int, destination: int, vnet: int,
           message_size: int) -> dict[str, int]:
    return {
        "cycle": cycle,
        "source": source,
        "destination": destination,
        "vnet": vnet,
        "message_size": message_size,
        "flits": (message_size + NI_FLIT_SIZE - 1) // NI_FLIT_SIZE,
    }


def replay_doc(name: str, nodes: int, mesh_rows: int, sim_cycles: int,
               drain_cycles: int, packets: list[dict[str, int]]) -> dict[str, object]:
    return {
        "schema": "pace.garnet.replay.v1",
        "name": name,
        "nodes": nodes,
        "mesh_rows": mesh_rows,
        "virtual_networks": VNETS,
        "ni_flit_size": NI_FLIT_SIZE,
        "sim_cycles": sim_cycles,
        "drain_cycles": drain_cycles,
        "packets": packets,
    }


def deterministic_mesh2x2() -> dict[str, object]:
    packets = [
        packet(0, 0, 3, 0, 8),
        packet(1, 1, 2, 0, 8),
        packet(3, 2, 1, 0, 8),
        packet(4, 3, 0, 0, 8),
        packet(8, 0, 2, 0, 8),
        packet(8, 1, 3, 0, 8),
    ]
    return replay_doc("deterministic_mesh2x2", 4, 2, 120, 200, packets)


def mesh4x4_long_paths() -> dict[str, object]:
    packets = [
        packet(0, 0, 15, 0, 8),
        packet(2, 15, 0, 0, 8),
        packet(4, 3, 12, 0, 8),
        packet(6, 12, 3, 0, 8),
        packet(8, 1, 14, 0, 8),
        packet(10, 14, 1, 0, 8),
        packet(12, 4, 11, 0, 8),
        packet(14, 11, 4, 0, 8),
    ]
    return replay_doc("mesh4x4_long_paths", 16, 4, 180, 260, packets)


def mesh4x4_contention() -> dict[str, object]:
    packets: list[dict[str, int]] = []
    for cycle in range(0, 12, 2):
        packets.extend([
            packet(cycle, 0, 15, 0, 8),
            packet(cycle, 1, 15, 0, 8),
            packet(cycle, 4, 15, 0, 8),
            packet(cycle, 5, 15, 0, 8),
        ])
    return replay_doc("mesh4x4_contention", 16, 4, 220, 320, packets)


def multi_vnet() -> dict[str, object]:
    packets = [
        packet(0, 0, 15, 0, 8),
        packet(0, 1, 14, 1, 8),
        packet(0, 2, 13, 2, 72),
        packet(4, 15, 0, 0, 8),
        packet(4, 14, 1, 1, 8),
        packet(4, 13, 2, 2, 72),
        packet(8, 5, 10, 0, 8),
        packet(8, 6, 9, 1, 8),
        packet(8, 7, 8, 2, 72),
    ]
    return replay_doc("multi_vnet", 16, 4, 180, 300, packets)


def multi_flit() -> dict[str, object]:
    packets = [
        packet(0, 0, 15, 2, 32),
        packet(2, 1, 14, 2, 72),
        packet(4, 2, 13, 2, 128),
        packet(6, 3, 12, 2, 160),
        packet(10, 12, 3, 2, 72),
        packet(12, 13, 2, 2, 128),
    ]
    return replay_doc("multi_flit", 16, 4, 220, 360, packets)


def burst_injection() -> dict[str, object]:
    packets = []
    for source in range(16):
        packets.append(packet(0, source, 15 - source, 0, 8))
    for source in range(16):
        packets.append(packet(1, source, (source + 8) % 16, 0, 8))
    return replay_doc("burst_injection", 16, 4, 220, 420, packets)


def drain_edge_cases() -> dict[str, object]:
    packets = [
        packet(0, 0, 3, 0, 8),
        packet(35, 1, 2, 0, 8),
        packet(38, 2, 1, 0, 8),
        packet(39, 3, 0, 0, 8),
    ]
    return replay_doc("drain_edge_cases", 4, 2, 40, 220, packets)


def mesh8x8_smoke() -> dict[str, object]:
    packets: list[dict[str, int]] = []
    pairs = [
        (0, 63), (7, 56), (8, 55), (15, 48),
        (16, 47), (24, 39), (31, 32), (63, 0),
    ]
    for idx, (source, destination) in enumerate(pairs):
        packets.append(packet(idx * 3, source, destination, 0, 8))
    return replay_doc("mesh8x8_smoke", 64, 8, 320, 520, packets)


def mesh4x4_multiflit_vnet0() -> dict[str, object]:
    packets = [
        packet(0, 0, 15, 0, 32),
        packet(2, 3, 12, 0, 64),
        packet(4, 5, 10, 0, 96),
        packet(6, 15, 0, 0, 128),
    ]
    return replay_doc("mesh4x4_multiflit_vnet0", 16, 4, 220, 360, packets)


SCENARIOS = {
    "deterministic-mesh2x2": deterministic_mesh2x2,
    "mesh4x4-long-paths": mesh4x4_long_paths,
    "mesh4x4-contention": mesh4x4_contention,
    "multi-vnet": multi_vnet,
    "multi-flit": multi_flit,
    "burst-injection": burst_injection,
    "drain-edge-cases": drain_edge_cases,
    "mesh8x8-smoke": mesh8x8_smoke,
    "mesh4x4-multiflit-vnet0": mesh4x4_multiflit_vnet0,
}


def scenario_names(tier: str) -> list[str]:
    quick = ["deterministic-mesh2x2"]
    standard = quick + [
        "mesh4x4-long-paths",
        "mesh4x4-contention",
        "multi-vnet",
        "multi-flit",
        "burst-injection",
        "drain-edge-cases",
    ]
    stress = standard + [
        "mesh8x8-smoke",
        "mesh4x4-multiflit-vnet0",
    ]
    if tier == "quick":
        return quick
    if tier == "standard":
        return standard
    if tier == "stress":
        return stress
    raise AssertionError(tier)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=sorted(SCENARIOS))
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--tier", choices=["quick", "standard", "stress"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.list:
        for name in sorted(SCENARIOS):
            print(name)
        return 0
    if args.output is None:
        parser.error("--output is required unless --list is used")

    selected = []
    if args.tier:
        selected = scenario_names(args.tier)
    elif args.scenario:
        selected = [args.scenario]
    else:
        selected = ["deterministic-mesh2x2"]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if len(selected) == 1:
        doc = SCENARIOS[selected[0]]()
        args.output.write_text(json.dumps(doc, indent=2) + "\n")
        print(f"wrote {args.output}")
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        for name in selected:
            doc = SCENARIOS[name]()
            path = args.output / f"{name}.replay.json"
            path.write_text(json.dumps(doc, indent=2) + "\n")
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
