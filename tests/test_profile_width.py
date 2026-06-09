#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "configs" / "example" / "garnet_synth_traffic.py"
PACE = ROOT / "pace-new"
OUT = ROOT / "verif" / "out" / "pace" / "profile_width"


def main() -> int:
    if not PACE.exists():
        raise RuntimeError("pace-new executable is missing; run make all first")

    OUT.mkdir(parents=True, exist_ok=True)
    topology = OUT / "mesh2x2_w256.json"
    profile = OUT / "bytes_profile.json"
    stats_path = OUT / "stats.json"
    flow_stats_path = OUT / "stats_flow.json"
    auto_stats_path = OUT / "stats_auto.json"

    _run([
        sys.executable,
        str(GENERATOR),
        "--num-cpus=4",
        "--num-dirs=0",
        "--network=garnet",
        "--topology=Mesh_XY",
        "--mesh-rows=2",
        "--sim-cycles=80",
        "--synthetic=uniform_random",
        "--injectionrate=0.0",
        "--link-width-bits=256",
        "--num-packets-max=0",
        "--output",
        str(topology),
    ])

    profile.write_text(json.dumps({
        "schema": "pace.component_traffic_profile.v1",
        "source": {
            "benchmark": "width_regression",
            "num_cpus": 4,
            "num_dirs": 0,
            "ni_flit_size_bytes": 16,
        },
        "scale": {
            "total_packets": 100,
            "total_flits": 500,
            "total_bytes": 7200,
            "sim_ticks": 50,
            "lambda_per_cpu": 0.5,
        },
        "traffic": {
            "vnet_packets": {"1": 100},
            "vnet_flits": {"1": 500},
            "packet_flits_by_vnet": {"1": {"5": 100}},
            "packet_bytes_by_vnet": {"1": {"72": 100}},
            "src_dst_ni_counts_by_vnet": {"1": {"0": {"3": 100}}},
            "src_dst_ni_flits_counts_by_vnet": {
                "1": {"0": {"3": {"5": 100}}},
            },
            "src_dst_ni_bytes_counts_by_vnet": {
                "1": {"0": {"3": {"72": 100}}},
            },
            "src_counts_by_vnet": {"1": {"0": 100}},
        },
        "burst": {
            "flow_interarrival_by_source_vnet_flits": {
                "0": {
                    "1": {
                        "5": {
                            "packets": 100,
                            "gaps": 99,
                            "mean_gap_cycles": 0.5,
                            "variance_gap_cycles": 1.0,
                            "cv": 2.0,
                        },
                    },
                },
            },
        },
    }, indent=2) + "\n")

    _run([
        str(PACE),
        "--topology-json",
        str(topology),
        "--simulate",
        "--traffic-profile-json",
        str(profile),
        "--profile-sim-cycles",
        "50",
        "--drain-cycles",
        "500",
        "--stats-json",
        str(stats_path),
    ])
    traffic = json.loads(stats_path.read_text())["traffic"]
    delivered = int(traffic["delivered_packets"])
    if delivered <= 0:
        raise AssertionError(traffic)
    expected_flits = delivered * 3
    if int(traffic["delivered_flits"]) != expected_flits:
        raise AssertionError(traffic)
    if int(traffic["injected_flits"]) != int(traffic["injected_packets"]) * 3:
        raise AssertionError(traffic)

    _run([
        str(PACE),
        "--topology-json",
        str(topology),
        "--simulate",
        "--traffic-profile-json",
        str(profile),
        "--profile-sim-cycles",
        "50",
        "--profile-flow-timing",
        "--drain-cycles",
        "500",
        "--stats-json",
        str(flow_stats_path),
    ])
    flow_traffic = json.loads(flow_stats_path.read_text())["traffic"]
    flow_delivered = int(flow_traffic["delivered_packets"])
    if flow_delivered <= 0:
        raise AssertionError(flow_traffic)
    if int(flow_traffic["delivered_flits"]) != flow_delivered * 3:
        raise AssertionError(flow_traffic)
    if (int(flow_traffic["injected_flits"]) !=
            int(flow_traffic["injected_packets"]) * 3):
        raise AssertionError(flow_traffic)

    _run([
        str(PACE),
        "--topology-json",
        str(topology),
        "--simulate",
        "--traffic-profile-json",
        str(profile),
        "--profile-sim-cycles",
        "50",
        "--profile-flow-timing-auto",
        "--drain-cycles",
        "500",
        "--stats-json",
        str(auto_stats_path),
    ])
    auto_traffic = json.loads(auto_stats_path.read_text())["traffic"]
    auto_delivered = int(auto_traffic["delivered_packets"])
    if auto_delivered <= 0:
        raise AssertionError(auto_traffic)
    if int(auto_traffic["delivered_flits"]) != auto_delivered * 3:
        raise AssertionError(auto_traffic)

    print("profile_width: PASS")
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
