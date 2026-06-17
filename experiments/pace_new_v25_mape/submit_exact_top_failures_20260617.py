#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import subprocess
from pathlib import Path


SCR = Path("/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606")
EXP = Path("/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606")
SCRIPTS = EXP / "scripts"
FEATURES = SCR / "pace_flowtiming_eval" / "transfer_rootcause_features_20260617a.csv"
CAMPAIGNS = [
    SCR / "pace_flowtiming_eval" / "corrected_input_sourcetime_campaign_20260616o",
    SCR / "pace_flowtiming_eval" / "corrected_input_sourcetime_campaign_20260616p",
]
OUT = Path(os.environ.get(
    "PACE_EXACT_TOP_OUT",
    str(SCR / "pace_flowtiming_eval" / "exact_top_failures_20260617a"),
))
RUNNER = SCRIPTS / "run_flag_probe_20260616q.sh"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def target_flit_bytes(topology_json: Path) -> int:
    import json

    doc = json.loads(topology_json.read_text())
    return int(doc.get("network", {}).get("ni_flit_size", 16) or 16)


def normalize_target_profile(case_id: str, target_run_dir: Path,
                             topology_json: Path) -> Path:
    out = OUT / "profiles" / f"{safe_name(case_id)}.target_msgbytes.json"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "python3", str(SCRIPTS / "profile_normalize_message_bytes.py"),
        "--input", str(target_run_dir / "component_traffic_profile.json"),
        "--output", str(out),
        "--target-flit-bytes", str(target_flit_bytes(topology_json)),
    ], check=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-jobs", type=int, default=24)
    parser.add_argument("--per-list", type=int, default=16)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cases").mkdir(exist_ok=True)
    (OUT / "profiles").mkdir(exist_ok=True)
    (EXP / "logs").mkdir(parents=True, exist_ok=True)

    manifest: dict[str, dict[str, str]] = {}
    for campaign in CAMPAIGNS:
        for row in read_csv(campaign / "manifest.csv"):
            manifest.setdefault(row["case_id"], row)

    feature_rows = [
        row for row in read_csv(FEATURES)
        if row.get("case_id") in manifest
    ]
    chosen: dict[str, dict[str, str]] = {}
    for key in ("avg_abs_err", "p99_abs_err"):
        for row in sorted(
            feature_rows, key=lambda r: float(r.get(key, 0.0)),
            reverse=True,
        )[:args.per_list]:
            chosen.setdefault(row["case_id"], row)
    chosen_rows = list(chosen.values())[:args.max_jobs]

    jobs: list[dict[str, str]] = []
    for row in chosen_rows:
        case_id = row["case_id"]
        meta = manifest[case_id]
        target = Path(meta["target_run_dir"])
        topology = Path(meta["topology_json"])
        profile = normalize_target_profile(case_id, target, topology)
        exact_case = f"{safe_name(case_id)}_exact_target"
        case_dir = OUT / "cases" / exact_case
        env = os.environ.copy()
        env.update({
            "CASE_DIR": str(case_dir),
            "CASE": exact_case,
            "MODE": "exact_target",
            "TOPOLOGY": str(topology),
            "PROFILE": str(profile),
            "TRUTH": str(target / "pace_profiler_extra.json"),
            "FLAGS": "--profile-flow-timing-auto",
        })
        job_id = subprocess.check_output(
            ["sbatch", "--parsable", str(RUNNER)], env=env, text=True,
        ).strip().split(";")[0]
        jobs.append({
            "job_id": job_id,
            "case_id": case_id,
            "exact_case": exact_case,
            "bench": row.get("bench", ""),
            "topo_label": row.get("topo_label", ""),
            "avg_abs_err": row.get("avg_abs_err", ""),
            "p99_abs_err": row.get("p99_abs_err", ""),
            "class_l1_profile_target": row.get("class_l1_profile_target", ""),
            "profile_json": str(profile),
            "topology_json": str(topology),
            "target_run_dir": str(target),
        })

    fields = list(jobs[0]) if jobs else [
        "job_id", "case_id", "exact_case", "bench", "topo_label",
        "avg_abs_err", "p99_abs_err", "class_l1_profile_target",
        "profile_json", "topology_json", "target_run_dir",
    ]
    with (OUT / "jobs.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"out={OUT}")
    print(f"submitted={len(jobs)}")
    for row in jobs:
        print(f"{row['job_id']},{row['case_id']},{row['exact_case']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
