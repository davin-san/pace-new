#!/usr/bin/env python3
"""Topology matrix validator for nontrivial package layouts.

These cases are intentionally small. They prove that the generic topology JSON
path can instantiate and move replay traffic through representative 2.5D, 3D,
heterogeneous, and irregular non-mesh designs.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "configs" / "example" / "garnet_synth_traffic.py"
PACE = ROOT / "pace-new"
OUT = ROOT / "verif" / "out" / "topology_matrix"


CASES = [
    {
        "name": "chiplet_2p5d",
        "num_cpus": 4,
        "chiplet_spec": ROOT / "configs" / "chiplets" / "example_2p5d.json",
        "sim_cycles": 180,
        "drain_cycles": 360,
        "packets": [
            {"cycle": 0, "source": 0, "destination": 2, "vnet": 0,
             "message_size": 8, "flits": 1},
            {"cycle": 4, "source": 3, "destination": 1, "vnet": 1,
             "message_size": 8, "flits": 1},
            {"cycle": 8, "source": 0, "destination": 3, "vnet": 2,
             "message_size": 72, "flits": 5},
        ],
        "features": ["interposer", "cdc", "serdes"],
    },
    {
        "name": "chiplet_3d_stack",
        "num_cpus": 6,
        "chiplet_spec": ROOT / "configs" / "chiplets" / "example_3d.json",
        "sim_cycles": 220,
        "drain_cycles": 420,
        "packets": [
            {"cycle": 0, "source": 0, "destination": 5, "vnet": 0,
             "message_size": 8, "flits": 1},
            {"cycle": 3, "source": 1, "destination": 4, "vnet": 1,
             "message_size": 8, "flits": 1},
            {"cycle": 6, "source": 4, "destination": 3, "vnet": 2,
             "message_size": 72, "flits": 5},
        ],
        "features": ["vertical", "cdc", "serdes"],
    },
    {
        "name": "irregular_nonmesh",
        "num_cpus": 5,
        "chiplet_spec": ROOT / "configs" / "chiplets" / "irregular_nonmesh.json",
        "sim_cycles": 240,
        "drain_cycles": 480,
        "packets": [
            {"cycle": 0, "source": 0, "destination": 2, "vnet": 0,
             "message_size": 8, "flits": 1},
            {"cycle": 2, "source": 1, "destination": 3, "vnet": 1,
             "message_size": 8, "flits": 1},
            {"cycle": 4, "source": 3, "destination": 0, "vnet": 2,
             "message_size": 72, "flits": 5},
        ],
        "features": ["custom_ports", "supported_vnets", "cdc", "serdes"],
    },
]


def main() -> int:
    if not PACE.exists():
        raise RuntimeError("pace-new executable is missing; run make all first")

    for case in CASES:
        validate_case(case)
        print(f"  PASS {case['name']}")
    print("topology_matrix: PASS")
    return 0


def validate_case(case: dict[str, object]) -> None:
    name = str(case["name"])
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    topology_path = out / "topology.json"
    replay_path = out / "replay.json"
    stats_path = out / "stats.json"
    trace_path = out / "trace.jsonl"

    _run([
        sys.executable,
        str(GENERATOR),
        "--num-cpus", str(case["num_cpus"]),
        "--num-dirs", "0",
        "--network", "garnet",
        "--topology", "HeteroChiplet",
        "--chiplet-spec", str(case["chiplet_spec"]),
        "--sim-cycles", str(case["sim_cycles"]),
        "--synthetic", "uniform_random",
        "--injectionrate", "0.0",
        "--num-packets-max", "0",
        "--output", str(topology_path),
    ])
    topology = json.loads(topology_path.read_text())
    validate_topology_features(topology["network"], case["features"])

    replay = {
        "schema": "pace.garnet.replay.v1",
        "name": name,
        "nodes": int(case["num_cpus"]),
        "virtual_networks": 3,
        "ni_flit_size": 16,
        "sim_cycles": int(case["sim_cycles"]),
        "drain_cycles": int(case["drain_cycles"]),
        "packets": case["packets"],
    }
    replay_path.write_text(json.dumps(replay, indent=2) + "\n")

    _run([
        str(PACE),
        "--topology-json", str(topology_path),
        "--simulate",
        "--replay-json", str(replay_path),
        "--stats-json", str(stats_path),
        "--trace-jsonl", str(trace_path),
    ])

    stats = json.loads(stats_path.read_text())
    validate_stats(replay, stats)
    validate_replay_trace(replay, trace_path)


def validate_topology_features(network: dict[str, object],
                               features: object) -> None:
    feature_set = set(features)
    int_links = network["int_links"]
    ext_links = network["ext_links"]

    if "interposer" in feature_set:
        assert any("Interposer" in link["src_outport"] for link in int_links)
    if "vertical" in feature_set:
        assert any(link["src_outport"] == "Up" for link in int_links)
        assert any(link["src_outport"] == "Down" for link in int_links)
    if "custom_ports" in feature_set:
        assert all(
            link["src_outport"] not in ("East", "West", "North", "South")
            for link in int_links
        )
    if "supported_vnets" in feature_set:
        assert any(link["supported_vnets"] == [1] for link in int_links)
    if "cdc" in feature_set:
        assert (
            any(link["src_cdc"] or link["dst_cdc"] for link in int_links) or
            any(link["ext_cdc"] or link["int_cdc"] for link in ext_links)
        )
    if "serdes" in feature_set:
        assert (
            any(link["src_serdes"] or link["dst_serdes"] for link in int_links) or
            any(link["ext_serdes"] or link["int_serdes"] for link in ext_links)
        )


def validate_stats(replay: dict[str, object], stats: dict[str, object]) -> None:
    packets = replay["packets"]
    by_vnet = Counter(int(packet["vnet"]) for packet in packets)
    flits_by_vnet = Counter()
    for packet in packets:
        flits_by_vnet[int(packet["vnet"])] += int(packet["flits"])

    expected_packets = len(packets)
    expected_flits = sum(int(packet["flits"]) for packet in packets)
    traffic = stats["traffic"]
    assert traffic["attempted_packets"] == expected_packets
    assert traffic["injected_packets"] == expected_packets
    assert traffic["delivered_packets"] == expected_packets
    assert traffic["injected_flits"] == expected_flits
    assert traffic["delivered_flits"] == expected_flits
    assert traffic["injected_by_vnet"] == _nonzero_map(by_vnet)
    assert traffic["delivered_by_vnet"] == _nonzero_map(by_vnet)
    assert traffic["injected_flits_by_vnet"] == _nonzero_map(flits_by_vnet)
    assert traffic["delivered_flits_by_vnet"] == _nonzero_map(flits_by_vnet)
    assert stats["garnet"]["total_link_utilization"] > 0


def validate_replay_trace(replay: dict[str, object], trace_path: Path) -> None:
    events = [json.loads(line) for line in trace_path.read_text().splitlines()]
    injects = [event for event in events if event["event"] == "replay.inject"]
    delivers = [event for event in events if event["event"] == "replay.deliver"]
    packets = sorted(replay["packets"], key=lambda packet: int(packet["cycle"]))
    assert len(injects) == len(packets)
    assert len(delivers) == len(packets)

    for event, packet in zip(injects, packets):
        assert int(event["tick"]) == int(packet["cycle"])
        assert int(event["source"]) == int(packet["source"])
        assert int(event["destination"]) == int(packet["destination"])
        assert int(event["vnet"]) == int(packet["vnet"])
        assert int(event["message_size"]) == int(packet["message_size"])
        assert int(event["flits"]) == int(packet["flits"])

    expected = Counter(
        (
            int(packet["destination"]),
            int(packet["vnet"]),
            int(packet["message_size"]),
            int(packet["flits"]),
        )
        for packet in packets
    )
    actual = Counter(
        (
            int(event["node"]),
            int(event["vnet"]),
            int(event["message_size"]),
            int(event["flits"]),
        )
        for event in delivers
    )
    assert actual == expected


def _nonzero_map(values: Counter[int]) -> dict[str, int]:
    return {str(key): value for key, value in sorted(values.items()) if value}


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
