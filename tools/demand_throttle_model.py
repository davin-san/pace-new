#!/usr/bin/env python3
"""Prototype demand-throttle model from one baseline profile.

The model is deliberately simple: if a workload has little outstanding memory
pressure in the baseline run, topology latency should not strongly reduce
network demand.  If it is already MSHR-heavy, higher network latency reduces
progress roughly according to Little's law.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _load_profile(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_extra(path: Path) -> dict:
    return json.loads(path.read_text())


def _mean_cpu_mshr(profile: dict) -> float:
    source = profile.get("source", {})
    num_cpus = int(source.get("num_cpus", 0) or 0)
    occ = profile.get("mshr", {}).get("avg_occupancy_by_node", {})
    values = []
    for node, value in occ.items():
        node_id = int(node)
        if num_cpus <= 0 or node_id < num_cpus:
            values.append(float(value))
    if not values:
        return 0.0
    return sum(values) / len(values)


def predict_ratio(
    baseline_profile: dict,
    baseline_latency: float,
    target_latency: float,
) -> tuple[float, float, float]:
    slots = float(baseline_profile.get("mshr", {}).get("slots", 16) or 16)
    mean_mshr = _mean_cpu_mshr(baseline_profile)
    pressure = max(0.0, min(1.0, mean_mshr / slots))
    sensitivity = math.sqrt(pressure)
    latency_ratio = baseline_latency / target_latency if target_latency > 0 else 1.0
    ratio = 1.0 - sensitivity * (1.0 - latency_ratio)
    return max(0.0, min(1.0, ratio)), pressure, sensitivity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-profile", required=True, type=Path)
    parser.add_argument("--baseline-extra", required=True, type=Path)
    parser.add_argument("--target-extra", required=True, type=Path)
    parser.add_argument("--target-profile", type=Path)
    parser.add_argument("--label", default="case")
    args = parser.parse_args()

    baseline_profile = _load_profile(args.baseline_profile)
    baseline_extra = _load_extra(args.baseline_extra)
    target_extra = _load_extra(args.target_extra)
    baseline_latency = float(baseline_extra.get("avg_packet_latency_cycles", 0.0) or 0.0)
    target_latency = float(target_extra.get("avg_packet_latency_cycles", 0.0) or 0.0)
    predicted, pressure, sensitivity = predict_ratio(
        baseline_profile, baseline_latency, target_latency)

    actual = None
    if args.target_profile:
        base_packets = float(
            baseline_profile.get("scale", {}).get("total_packets", 0) or 0)
        target_packets = float(
            _load_profile(args.target_profile).get("scale", {}).get(
                "total_packets", 0) or 0)
        if base_packets > 0:
            actual = target_packets / base_packets

    print("metric,value")
    print(f"label,{args.label}")
    print(f"baseline_latency,{baseline_latency:.6f}")
    print(f"target_latency,{target_latency:.6f}")
    print(f"latency_ratio_base_over_target,{baseline_latency / target_latency:.6f}")
    print(f"baseline_cpu_mshr_pressure,{pressure:.6f}")
    print(f"feedback_sensitivity,{sensitivity:.6f}")
    print(f"predicted_demand_ratio,{predicted:.6f}")
    if actual is not None:
        print(f"actual_demand_ratio,{actual:.6f}")
        print(f"ratio_error_pct,{100.0 * (predicted - actual) / actual:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
