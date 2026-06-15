#!/usr/bin/env python3
"""Compare phase-level traffic shape across gem5-derived PACE profiles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _vnet_pct(phase: dict[str, Any], vnet: str) -> float:
    total = float(phase.get("total_packets", 0) or 0)
    if total <= 0:
        return 0.0
    return 100.0 * float(phase.get("vnet_packets", {}).get(vnet, 0)) / total


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    phases = data.get("phases", [])
    total = float(data.get("total_packets", 0) or 0)
    cumulative = 0.0
    rows = []
    for index, phase in enumerate(phases):
        packets = float(phase.get("total_packets", 0) or 0)
        cumulative += packets
        rows.append({
            "phase": index,
            "packets": packets,
            "cum_pct": 100.0 * cumulative / total if total else 0.0,
            "data_pct": float(phase.get("data_pct", 0) or 0),
            "v0_pct": _vnet_pct(phase, "0"),
            "v1_pct": _vnet_pct(phase, "1"),
            "v2_pct": _vnet_pct(phase, "2"),
            "lambda": float(phase.get("lambda", 0) or 0),
            "sim_ticks": float(phase.get("sim_ticks", 0) or 0),
        })
    return {"total_packets": total, "sim_ticks": data.get("sim_ticks", 0), "rows": rows}


def _corr(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)
    if dx <= 0.0 or dy <= 0.0:
        return 0.0
    return num / (dx * dy) ** 0.5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profiles", nargs="+", type=Path)
    parser.add_argument("--labels", help="Comma-separated labels.")
    args = parser.parse_args()

    labels = (
        [label.strip() for label in args.labels.split(",")]
        if args.labels else [path.parent.name for path in args.profiles]
    )
    if len(labels) != len(args.profiles):
        raise SystemExit("--labels must match profile count")

    loaded = [_load(path) for path in args.profiles]
    print("summary_metric," + ",".join(labels))
    print("total_packets," + ",".join(f"{p['total_packets']:.0f}" for p in loaded))
    print("sim_ticks," + ",".join(str(p["sim_ticks"]) for p in loaded))
    print("num_phases," + ",".join(str(len(p["rows"])) for p in loaded))

    base = loaded[0]["rows"]
    for label, profile in zip(labels[1:], loaded[1:]):
        common = min(len(base), len(profile["rows"]))
        metrics = ["packets", "data_pct", "v0_pct", "v1_pct", "v2_pct"]
        for metric in metrics:
            xs = [base[i][metric] for i in range(common)]
            ys = [profile["rows"][i][metric] for i in range(common)]
            print(f"corr_{labels[0]}_{label}_{metric},{_corr(xs, ys):.6f}")

    print()
    print("label,phase,packets,cum_pct,data_pct,v0_pct,v1_pct,v2_pct,lambda,sim_ticks")
    for label, profile in zip(labels, loaded):
        for row in profile["rows"]:
            print(
                f"{label},{row['phase']},{row['packets']:.0f},"
                f"{row['cum_pct']:.6f},{row['data_pct']:.6f},"
                f"{row['v0_pct']:.6f},{row['v1_pct']:.6f},"
                f"{row['v2_pct']:.6f},{row['lambda']:.8f},"
                f"{row['sim_ticks']:.0f}"
            )


if __name__ == "__main__":
    main()
