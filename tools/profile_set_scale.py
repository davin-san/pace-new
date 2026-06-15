#!/usr/bin/env python3
"""Write a copy of a component traffic profile with updated scale metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sim-cycles", type=int)
    parser.add_argument("--clock-period-ticks", type=int)
    parser.add_argument("--lambda-per-cpu", type=float)
    args = parser.parse_args()

    profile = json.loads(args.input.read_text())
    scale = profile.setdefault("scale", {})
    if args.sim_cycles is not None:
        scale["sim_cycles"] = int(args.sim_cycles)
    if args.clock_period_ticks is not None:
        scale["clock_period_ticks"] = int(args.clock_period_ticks)
    if args.lambda_per_cpu is not None:
        scale["lambda_per_cpu"] = float(args.lambda_per_cpu)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
