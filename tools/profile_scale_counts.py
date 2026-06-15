#!/usr/bin/env python3
"""Scale count fields in a component traffic profile.

This is an analysis helper for testing demand-feedback hypotheses. It preserves
traffic composition while changing offered demand; it is not a simulator change.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _scale_leaf(value: Any, factor: float) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(round(value * factor))
    if isinstance(value, float):
        return value * factor
    if isinstance(value, dict):
        return {key: _scale_leaf(child, factor) for key, child in value.items()}
    if isinstance(value, list):
        return [_scale_leaf(child, factor) for child in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target-packets", required=True, type=int)
    parser.add_argument("--sim-cycles", type=int)
    parser.add_argument("--lambda-per-cpu", type=float)
    args = parser.parse_args()

    profile = json.loads(args.input.read_text())
    scale = profile.setdefault("scale", {})
    source_packets = int(scale.get("total_packets", 0) or 0)
    if source_packets <= 0:
        raise SystemExit("input profile scale.total_packets must be positive")
    factor = args.target_packets / source_packets

    for section in ("traffic", "phases"):
        if section in profile:
            profile[section] = _scale_leaf(profile[section], factor)
    if "burst" in profile and "flow_interarrival_by_source_vnet_flits" in profile["burst"]:
        flows = profile["burst"]["flow_interarrival_by_source_vnet_flits"]
        for by_vnet in flows.values():
            for by_flits in by_vnet.values():
                for stats in by_flits.values():
                    if "packets" in stats:
                        stats["packets"] = int(round(int(stats["packets"]) * factor))
                    if "gaps" in stats:
                        stats["gaps"] = max(0, int(stats["packets"]) - 1)

    scale["total_packets"] = int(args.target_packets)
    for key in ("total_flits", "total_bytes"):
        if key in scale:
            scale[key] = int(round(int(scale[key]) * factor))
    if args.sim_cycles is not None:
        scale["sim_cycles"] = int(args.sim_cycles)
    if args.lambda_per_cpu is not None:
        scale["lambda_per_cpu"] = float(args.lambda_per_cpu)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
