#!/usr/bin/env python3
"""Build latency MAPE summaries from gem5 profiler and PACE stats JSON.

gem5's PaceProfiler records Garnet packet network latency on tail ejection:
dequeue_time - enqueue_time - one cycle.  The matching PACE metric is
traffic.avg_packet_network_latency_cycles and
traffic.p99_packet_network_latency_cycles.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Case:
    label: str
    gem5_path: Path
    pace_path: Path


def _pct_error(predicted: float, truth: float) -> float:
    if truth == 0.0:
        return 0.0 if predicted == 0.0 else float("inf")
    return 100.0 * (predicted - truth) / truth


def _load_case(spec: str) -> Case:
    parts = spec.split(":", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "case must be label:gem5_profiler_extra.json:pace_stats.json")
    return Case(parts[0], Path(parts[1]), Path(parts[2]))


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise SystemExit(f"missing file: {path}") from exc


def _row(case: Case) -> dict[str, object]:
    gem5 = _read_json(case.gem5_path)
    pace = _read_json(case.pace_path)
    traffic = pace.get("traffic", {})

    gem5_avg = float(gem5.get("avg_packet_latency_cycles", 0.0))
    gem5_p99 = float(gem5.get("p99_packet_latency_cycles", 0.0))
    pace_avg = float(traffic.get("avg_packet_network_latency_cycles", 0.0))
    pace_p99 = float(traffic.get("p99_packet_network_latency_cycles", 0.0))
    avg_err = _pct_error(pace_avg, gem5_avg)
    p99_err = _pct_error(pace_p99, gem5_p99)
    return {
        "case": case.label,
        "gem5_avg": gem5_avg,
        "pace_avg": pace_avg,
        "avg_err_pct": avg_err,
        "avg_abs_err_pct": abs(avg_err),
        "gem5_p99": gem5_p99,
        "pace_p99": pace_p99,
        "p99_err_pct": p99_err,
        "p99_abs_err_pct": abs(p99_err),
        "gem5_packets": int(gem5.get("total_pkts_profiled", 0) or 0),
        "pace_packets": int(traffic.get("delivered_packets", 0) or 0),
        "gem5_profile": str(case.gem5_path),
        "pace_stats": str(case.pace_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        action="append",
        type=_load_case,
        required=True,
        help="label:gem5_profiler_extra.json:pace_stats.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = [_row(case) for case in args.case]
    avg_mape = sum(float(row["avg_abs_err_pct"]) for row in rows) / len(rows)
    p99_mape = sum(float(row["p99_abs_err_pct"]) for row in rows) / len(rows)

    fieldnames = [
        "case",
        "gem5_avg",
        "pace_avg",
        "avg_err_pct",
        "avg_abs_err_pct",
        "gem5_p99",
        "pace_p99",
        "p99_err_pct",
        "p99_abs_err_pct",
        "gem5_packets",
        "pace_packets",
        "gem5_profile",
        "pace_stats",
    ]

    out_file = args.output.open("w", newline="") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(out_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        writer.writerow({
            "case": "MAPE",
            "avg_abs_err_pct": avg_mape,
            "p99_abs_err_pct": p99_mape,
        })
    finally:
        if args.output:
            out_file.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
