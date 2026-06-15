#!/usr/bin/env python3
"""Run PACE transfer cases and summarize latency error.

Each case is:

    label:topology.json:component_profile.json:gem5_profiler_extra.json

The runner is deliberately profile-format aware but simulator-agnostic: it
does not tune Garnet knobs.  If a profile contains exact phase-conditioned
endpoint counts, the runner enables `--profile-phased`; otherwise it leaves
phase replay off because marginal-only phase metadata is not a valid traffic
contract.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Case:
    label: str
    topology: Path
    profile: Path
    gem5_extra: Path


def _parse_case(spec: str) -> Case:
    parts = spec.split(":", 3)
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "case must be label:topology.json:profile.json:gem5_extra.json")
    return Case(parts[0], Path(parts[1]), Path(parts[2]), Path(parts[3]))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _has_exact_phase_counts(profile: dict) -> bool:
    for phase in profile.get("phases", []):
        if phase.get("src_dst_ni_flits_counts_by_vnet") or phase.get(
            "src_dst_ni_bytes_counts_by_vnet"):
            return True
    return False


def _pct_error(predicted: float, truth: float) -> float:
    if truth == 0.0:
        return 0.0 if predicted == 0.0 else float("inf")
    return 100.0 * (predicted - truth) / truth


def _run_case(args: argparse.Namespace, case: Case) -> dict[str, object]:
    profile = _read_json(case.profile)
    stats_path = args.output_dir / f"stats_{case.label}.json"
    cmd = [
        str(args.pace_bin),
        "--topology-json", str(case.topology),
        "--simulate",
        "--traffic-profile-json", str(case.profile),
        "--profile-flow-timing-auto",
        "--drain-cycles", str(args.drain_cycles),
        "--stats-json", str(stats_path),
    ]
    if _has_exact_phase_counts(profile):
        cmd.insert(cmd.index("--profile-flow-timing-auto"), "--profile-phased")
    subprocess.run(cmd, check=True, cwd=args.cwd)

    gem5 = _read_json(case.gem5_extra)
    pace = _read_json(stats_path)
    traffic = pace.get("traffic", {})
    gem5_avg = float(gem5.get("avg_packet_latency_cycles", 0.0))
    gem5_p99 = float(gem5.get("p99_packet_latency_cycles", 0.0))
    pace_avg = float(traffic.get("avg_packet_network_latency_cycles", 0.0))
    pace_p99 = float(traffic.get("p99_packet_network_latency_cycles", 0.0))
    avg_err = _pct_error(pace_avg, gem5_avg)
    p99_err = _pct_error(pace_p99, gem5_p99)
    return {
        "case": case.label,
        "phase_mode": "exact" if _has_exact_phase_counts(profile) else "off",
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
        "topology": str(case.topology),
        "profile": str(case.profile),
        "pace_stats": str(stats_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pace-bin", type=Path, default=Path("./pace-new"))
    parser.add_argument("--cwd", type=Path, default=Path("."))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--drain-cycles", type=int, default=20000)
    parser.add_argument("--case", action="append", type=_parse_case, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = [_run_case(args, case) for case in args.case]
    avg_mape = sum(float(row["avg_abs_err_pct"]) for row in rows) / len(rows)
    p99_mape = sum(float(row["p99_abs_err_pct"]) for row in rows) / len(rows)
    summary = args.summary or args.output_dir / "summary_transfer_matrix.csv"
    with summary.open("w", newline="") as out:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        writer.writerow({
            "case": "MAPE",
            "avg_abs_err_pct": avg_mape,
            "p99_abs_err_pct": p99_mape,
        })
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
