#!/usr/bin/env python3
"""Report topology feedback effects between two full-system profiles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    traffic = data.get("traffic", {}).get("packet_flits_by_vnet", {})
    classes: dict[tuple[int, int], int] = {}
    total = 0
    for vnet, hist in traffic.items():
        for flits, count in hist.items():
            key = (int(vnet), int(flits))
            classes[key] = classes.get(key, 0) + int(count)
            total += int(count)
    scale = data.get("scale", {})
    return {
        "total_packets": int(scale.get("total_packets", total) or total),
        "total_flits": int(scale.get("total_flits", 0) or 0),
        "sim_cycles": int(scale.get("sim_cycles", 0) or 0),
        "lambda_per_cpu": float(scale.get("lambda_per_cpu", 0.0) or 0.0),
        "classes": classes,
    }


def _extra(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    return {
        "avg": float(data.get("avg_packet_latency_cycles", 0.0) or 0.0),
        "p99": float(data.get("p99_packet_latency_cycles", 0.0) or 0.0),
    }


def _pct(count: int, total: int) -> float:
    return 100.0 * count / total if total else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-profile", required=True, type=Path)
    parser.add_argument("--target-profile", required=True, type=Path)
    parser.add_argument("--base-extra", type=Path)
    parser.add_argument("--target-extra", type=Path)
    parser.add_argument("--label", default="case")
    args = parser.parse_args()

    base = _load(args.base_profile)
    target = _load(args.target_profile)
    base_extra = _extra(args.base_extra) if args.base_extra else {"avg": 0.0, "p99": 0.0}
    target_extra = _extra(args.target_extra) if args.target_extra else {"avg": 0.0, "p99": 0.0}

    demand_ratio = (
        target["total_packets"] / base["total_packets"]
        if base["total_packets"] else 0.0
    )
    latency_ratio = (
        target_extra["avg"] / base_extra["avg"]
        if base_extra["avg"] else 0.0
    )
    print("metric,value")
    print(f"label,{args.label}")
    print(f"base_packets,{base['total_packets']}")
    print(f"target_packets,{target['total_packets']}")
    print(f"demand_ratio_target_over_base,{demand_ratio:.6f}")
    print(f"demand_drop_pct,{100.0 * (1.0 - demand_ratio):.6f}")
    print(f"base_lambda_per_cpu,{base['lambda_per_cpu']:.8f}")
    print(f"target_lambda_per_cpu,{target['lambda_per_cpu']:.8f}")
    print(f"base_avg_network_latency,{base_extra['avg']:.6f}")
    print(f"target_avg_network_latency,{target_extra['avg']:.6f}")
    print(f"latency_ratio_target_over_base,{latency_ratio:.6f}")
    print()
    print("class,vnet,flits,base_pct,target_pct,delta_pct_points")
    keys = sorted(set(base["classes"]) | set(target["classes"]))
    for vnet, flits in keys:
        base_pct = _pct(base["classes"].get((vnet, flits), 0), base["total_packets"])
        target_pct = _pct(target["classes"].get((vnet, flits), 0), target["total_packets"])
        print(
            f"v{vnet}_f{flits},{vnet},{flits},"
            f"{base_pct:.6f},{target_pct:.6f},{target_pct - base_pct:.6f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
