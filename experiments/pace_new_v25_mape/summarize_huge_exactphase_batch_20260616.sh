#!/bin/bash
#SBATCH --job-name=huge-summarize
#SBATCH --account=gts-chao33
#SBATCH --partition=cpu-small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/logs/huge-summarize_%j.out
#SBATCH --error=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/logs/huge-summarize_%j.err

set -eo pipefail

SCR=/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606
TAG=${TAG:-exactphase_hugebatch_20260616a}
MANIFEST=$SCR/fullsys_flowstats_exactphase/${TAG}_manifest.csv
SUMMARY=$SCR/fullsys_flowstats_exactphase/${TAG}_summary.csv

python3 - "$SCR" "$MANIFEST" "$SUMMARY" <<'PY'
import csv
import json
import sys
from pathlib import Path

scratch = Path(sys.argv[1])
manifest = Path(sys.argv[2])
summary = Path(sys.argv[3])

fieldnames = [
    "job_id", "bench", "topo_label", "group", "status",
    "run_dir", "exact_extra_phases", "exact_profile_phases",
    "gem5_packets", "profile_packets", "gem5_avg", "gem5_p99",
    "error",
]

def run_dir(row):
    return scratch / "fullsys_flowstats_exactphase" / (
        f"{row['bench']}_c{row['num_cpus']}_l2{row['l2_size']}"
        f"_d{row['num_dirs']}_mc{row['mem_channels']}_{row['topo_label']}"
        f"_ll{row['link_latency']}_rl{row['router_latency']}"
        f"_w{row['link_width_bits']}_{row['tag']}"
    )

def count_profile_phases(profile):
    return sum(
        1 for phase in profile.get("phases", [])
        if phase.get("src_dst_ni_flits_counts_by_vnet")
    )

rows = []
with manifest.open(newline="") as fh:
    reader = csv.DictReader(fh)
    for row in reader:
        rd = run_dir(row)
        out = {
            "job_id": row["job_id"],
            "bench": row["bench"],
            "topo_label": row["topo_label"],
            "group": row["group"],
            "status": "missing",
            "run_dir": str(rd),
            "exact_extra_phases": 0,
            "exact_profile_phases": 0,
            "gem5_packets": "",
            "profile_packets": "",
            "gem5_avg": "",
            "gem5_p99": "",
            "error": "",
        }
        extra_path = rd / "pace_profiler_extra.json"
        profile_path = rd / "component_traffic_profile.json"
        try:
            if not extra_path.exists():
                raise FileNotFoundError(extra_path)
            extra = json.loads(extra_path.read_text())
            out["exact_extra_phases"] = len(
                extra.get("phase_src_dst_ni_flits_counts_by_vnet", [])
            )
            out["gem5_packets"] = extra.get("total_pkts_profiled", "")
            out["gem5_avg"] = extra.get("avg_packet_latency_cycles", "")
            out["gem5_p99"] = extra.get("p99_packet_latency_cycles", "")
            if not profile_path.exists():
                raise FileNotFoundError(profile_path)
            profile = json.loads(profile_path.read_text())
            out["exact_profile_phases"] = count_profile_phases(profile)
            out["profile_packets"] = profile.get("scale", {}).get(
                "total_packets", "")
            out["status"] = (
                "ok" if out["exact_extra_phases"] and out["exact_profile_phases"]
                else "missing_exact_phase"
            )
        except Exception as exc:
            out["error"] = str(exc)
        rows.append(out)

summary.parent.mkdir(parents=True, exist_ok=True)
with summary.open("w", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

counts = {}
for row in rows:
    counts[row["status"]] = counts.get(row["status"], 0) + 1
print(f"summary={summary}")
for key in sorted(counts):
    print(f"{key}={counts[key]}")
PY
