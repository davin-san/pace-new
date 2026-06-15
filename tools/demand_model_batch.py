#!/usr/bin/env python3
"""Batch wrapper for demand_throttle_model reports."""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

import demand_throttle_model


def _parse_report(text: str) -> dict[str, str]:
    rows = csv.reader(io.StringIO(text))
    out: dict[str, str] = {}
    next(rows, None)
    for key, value in rows:
        out[key] = value
    return out


def _run_case(spec: str) -> dict[str, str]:
    parts = spec.split(":", 4)
    if len(parts) != 5:
        raise SystemExit(
            "case must be label:base_profile:base_extra:target_extra:target_profile")
    label, base_profile, base_extra, target_extra, target_profile = parts
    profile = demand_throttle_model._load_profile(Path(base_profile))
    baseline_latency = float(
        demand_throttle_model._load_extra(Path(base_extra)).get(
            "avg_packet_latency_cycles", 0.0) or 0.0)
    target_latency = float(
        demand_throttle_model._load_extra(Path(target_extra)).get(
            "avg_packet_latency_cycles", 0.0) or 0.0)
    predicted, pressure, sensitivity, exponent = demand_throttle_model.predict_ratio(
        profile, baseline_latency, target_latency)
    target = demand_throttle_model._load_profile(Path(target_profile))
    actual = (
        float(target.get("scale", {}).get("total_packets", 0) or 0) /
        float(profile.get("scale", {}).get("total_packets", 1) or 1)
    )
    phase_cv = demand_throttle_model._phase_lambda_cv(profile)
    return {
        "case": label,
        "baseline_latency": f"{baseline_latency:.6f}",
        "target_latency": f"{target_latency:.6f}",
        "baseline_mshr_pressure": f"{pressure:.6f}",
        "baseline_phase_lambda_cv": f"{phase_cv:.6f}",
        "pressure_exponent": f"{exponent:.6f}",
        "feedback_sensitivity": f"{sensitivity:.6f}",
        "predicted_ratio": f"{predicted:.6f}",
        "actual_ratio": f"{actual:.6f}",
        "ratio_error_pct": f"{100.0 * (predicted - actual) / actual:.6f}",
        "ratio_abs_error_pct": f"{abs(100.0 * (predicted - actual) / actual):.6f}",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = [_run_case(spec) for spec in args.case]
    fieldnames = list(rows[0].keys())
    out = args.output.open("w", newline="") if args.output else None
    sink = out if out is not None else None
    try:
        writer = csv.DictWriter(sink or __import__("sys").stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        mean_abs = sum(float(row["ratio_abs_error_pct"]) for row in rows) / len(rows)
        writer.writerow({"case": "MAPE", "ratio_abs_error_pct": f"{mean_abs:.6f}"})
    finally:
        if out is not None:
            out.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
