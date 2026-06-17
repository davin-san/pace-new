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
    bursty_stats_path = OUT / "stats_bursty.json"
    flow_stats_path = OUT / "stats_flow.json"
    auto_stats_path = OUT / "stats_auto.json"
    scale_cycles_stats_path = OUT / "stats_scale_cycles.json"
    incomplete_phase_profile = OUT / "incomplete_phase_profile.json"
    incomplete_phase_stats_path = OUT / "stats_incomplete_phase.json"
    exact_phase_profile = OUT / "exact_phase_profile.json"
    exact_phase_stats_path = OUT / "stats_exact_phase.json"
    exact_phase_flow_profile = OUT / "exact_phase_flow_profile.json"
    exact_phase_flow_stats_path = OUT / "stats_exact_phase_flow.json"
    exact_phase_flow_trace_path = OUT / "trace_exact_phase_flow.jsonl"

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
            "sim_cycles": 50,
            "lambda_per_cpu": 0.1,
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
            "per_node_injection_cv": {"0": 4.0},
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
        "--profile-bursty",
        "--drain-cycles",
        "500",
        "--stats-json",
        str(bursty_stats_path),
    ])
    bursty_traffic = json.loads(bursty_stats_path.read_text())["traffic"]
    if int(bursty_traffic["injected_packets"]) != 100:
        raise AssertionError(bursty_traffic)
    if int(bursty_traffic["delivered_packets"]) != 100:
        raise AssertionError(bursty_traffic)
    if int(bursty_traffic["delivered_flits"]) != 300:
        raise AssertionError(bursty_traffic)

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

    _run([
        str(PACE),
        "--topology-json",
        str(topology),
        "--simulate",
        "--traffic-profile-json",
        str(profile),
        "--profile-flow-timing",
        "--drain-cycles",
        "500",
        "--stats-json",
        str(scale_cycles_stats_path),
    ])
    scale_cycles_stats = json.loads(scale_cycles_stats_path.read_text())
    if int(scale_cycles_stats["cycles"]) != 550:
        raise AssertionError(scale_cycles_stats)

    incomplete_phase_profile.write_text(json.dumps({
        "schema": "pace.component_traffic_profile.v1",
        "source": {
            "benchmark": "phase_coverage_regression",
            "num_cpus": 4,
            "num_dirs": 0,
            "ni_flit_size_bytes": 16,
        },
        "scale": {
            "total_packets": 200,
            "total_flits": 600,
            "total_bytes": 9600,
            "sim_cycles": 2000,
            "lambda_per_cpu": 0.025,
        },
        "traffic": {
            "vnet_packets": {"0": 100, "1": 100},
            "vnet_flits": {"0": 100, "1": 500},
            "packet_flits_by_vnet": {
                "0": {"1": 100},
                "1": {"5": 100},
            },
            "packet_bytes_by_vnet": {
                "0": {"16": 100},
                "1": {"80": 100},
            },
            "src_dst_ni_counts_by_vnet": {
                "0": {"0": {"3": 100}},
                "1": {"1": {"2": 100}},
            },
            "src_dst_ni_flits_counts_by_vnet": {
                "0": {"0": {"3": {"1": 100}}},
                "1": {"1": {"2": {"5": 100}}},
            },
            "src_dst_ni_bytes_counts_by_vnet": {
                "0": {"0": {"3": {"16": 100}}},
                "1": {"1": {"2": {"80": 100}}},
            },
            "src_counts_by_vnet": {
                "0": {"0": 100},
                "1": {"1": 100},
            },
        },
        "phases": [{
            "index": 0,
            "sim_cycles": 2000,
            "total_packets": 200,
            "lambda": 0.1,
            "source_fractions": {"0": 1.0},
        }],
    }, indent=2) + "\n")

    _run([
        str(PACE),
        "--topology-json",
        str(topology),
        "--simulate",
        "--traffic-profile-json",
        str(incomplete_phase_profile),
        "--profile-phased",
        "--drain-cycles",
        "500",
        "--stats-json",
        str(incomplete_phase_stats_path),
    ])
    incomplete_phase_traffic = json.loads(
        incomplete_phase_stats_path.read_text())["traffic"]
    if int(incomplete_phase_traffic["delivered_by_vnet"].get("1", 0)) <= 0:
        raise AssertionError(incomplete_phase_traffic)

    exact_phase_profile.write_text(json.dumps({
        "schema": "pace.component_traffic_profile.v1",
        "source": {
            "benchmark": "exact_phase_regression",
            "num_cpus": 4,
            "num_dirs": 0,
            "ni_flit_size_bytes": 16,
        },
        "scale": {
            "total_packets": 20,
            "total_flits": 60,
            "total_bytes": 960,
            "sim_cycles": 2000,
            "lambda_per_cpu": 0.0025,
        },
        "traffic": {
            "vnet_packets": {"0": 10, "1": 10},
            "vnet_flits": {"0": 10, "1": 50},
            "packet_flits_by_vnet": {
                "0": {"1": 10},
                "1": {"5": 10},
            },
            "packet_bytes_by_vnet": {
                "0": {"16": 10},
                "1": {"80": 10},
            },
            "src_dst_ni_counts_by_vnet": {
                "0": {"0": {"3": 10}},
                "1": {"1": {"2": 10}},
            },
            "src_dst_ni_flits_counts_by_vnet": {
                "0": {"0": {"3": {"1": 10}}},
                "1": {"1": {"2": {"5": 10}}},
            },
            "src_dst_ni_bytes_counts_by_vnet": {
                "0": {"0": {"3": {"16": 10}}},
                "1": {"1": {"2": {"80": 10}}},
            },
            "src_counts_by_vnet": {
                "0": {"0": 10},
                "1": {"1": 10},
            },
        },
        "phases": [{
            "index": 0,
            "sim_cycles": 100,
            "total_packets": 20,
            "lambda": 0.2,
            "src_dst_ni_flits_counts_by_vnet": {
                "0": {"0": {"3": {"1": 10}}},
                "1": {"1": {"2": {"5": 10}}},
            },
        }],
    }, indent=2) + "\n")

    _run([
        str(PACE),
        "--topology-json",
        str(topology),
        "--simulate",
        "--traffic-profile-json",
        str(exact_phase_profile),
        "--profile-phased",
        "--drain-cycles",
        "100",
        "--stats-json",
        str(exact_phase_stats_path),
    ])
    exact_phase_stats = json.loads(exact_phase_stats_path.read_text())
    exact_phase_traffic = exact_phase_stats["traffic"]
    if int(exact_phase_stats["cycles"]) != 200:
        raise AssertionError(exact_phase_stats)
    if int(exact_phase_traffic["delivered_by_vnet"].get("0", 0)) <= 0:
        raise AssertionError(exact_phase_traffic)
    if int(exact_phase_traffic["delivered_by_vnet"].get("1", 0)) <= 0:
        raise AssertionError(exact_phase_traffic)

    exact_phase_flow_profile.write_text(json.dumps({
        "schema": "pace.component_traffic_profile.v1",
        "source": {
            "benchmark": "exact_phase_flow_regression",
            "num_cpus": 4,
            "num_dirs": 0,
            "ni_flit_size_bytes": 16,
        },
        "scale": {
            "total_packets": 40,
            "total_flits": 120,
            "total_bytes": 1920,
            "sim_cycles": 200,
            "lambda_per_cpu": 0.05,
        },
        "traffic": {
            "vnet_packets": {"0": 20, "1": 20},
            "vnet_flits": {"0": 20, "1": 100},
            "packet_flits_by_vnet": {
                "0": {"1": 20},
                "1": {"5": 20},
            },
            "src_dst_ni_flits_counts_by_vnet": {
                "0": {"0": {"3": {"1": 20}}},
                "1": {"1": {"2": {"5": 20}}},
            },
        },
        "burst": {
            "flow_interarrival_by_source_vnet_flits": {
                "0": {"0": {"1": {"cv": 0.0025}}},
                "1": {"1": {"5": {"cv": 0.0025}}},
            },
        },
        "phases": [
            {
                "phase_index": 0,
                "sim_cycles": 100,
                "total_packets": 20,
                "src_dst_ni_flits_counts_by_vnet": {
                    "0": {"0": {"3": {"1": 20}}},
                },
            },
            {
                "phase_index": 1,
                "sim_cycles": 100,
                "total_packets": 20,
                "src_dst_ni_flits_counts_by_vnet": {
                    "1": {"1": {"2": {"5": 20}}},
                },
            },
        ],
    }, indent=2) + "\n")

    _run([
        str(PACE),
        "--topology-json",
        str(topology),
        "--simulate",
        "--traffic-profile-json",
        str(exact_phase_flow_profile),
        "--profile-phased",
        "--profile-flow-timing",
        "--drain-cycles",
        "100",
        "--trace-jsonl",
        str(exact_phase_flow_trace_path),
        "--stats-json",
        str(exact_phase_flow_stats_path),
    ])
    flow_phase_injects = [
        event for event in (
            json.loads(line)
            for line in exact_phase_flow_trace_path.read_text().splitlines()
        )
        if event.get("event") == "profile.inject"
    ]
    if not flow_phase_injects:
        raise AssertionError("no profile.inject events")
    for event in flow_phase_injects:
        tick = int(event["tick"])
        vnet = int(event["vnet"])
        if vnet == 0 and tick >= 100:
            raise AssertionError(event)
        if vnet == 1 and tick < 100:
            raise AssertionError(event)

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
