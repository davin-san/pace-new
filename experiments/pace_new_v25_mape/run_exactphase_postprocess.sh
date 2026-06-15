#!/bin/bash
#SBATCH --job-name=exactphase-post
#SBATCH --account=gts-chao33
#SBATCH --partition=cpu-small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/logs/exactphase-post_%j.out
#SBATCH --error=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/logs/exactphase-post_%j.err

set -eo pipefail

SCR=/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606
WT=$SCR/pace_new_worktrees/phase_condition_20260615
EVAL=$SCR/pace_flowtiming_eval/exactphase_transfer_20260615

TOPO_T1=$SCR/pace_flowtiming_eval/blackscholes_t1_inter25_20260609/topology.json

DEDUP_T0=$SCR/fullsys_flowstats_exactphase/dedup_c16_l2256kB_d4_mc1_T0_mesh_ll1_rl1_w128_exactphase_base_20260615
CANNEAL_T0=$SCR/fullsys_flowstats_exactphase/canneal_c16_l2256kB_d4_mc1_T0_mesh_ll1_rl1_w128_exactphase_base_20260615
BLACKSCHOLES_T0=$SCR/fullsys_flowstats_exactphase/blackscholes_c16_l2256kB_d4_mc1_T0_mesh_ll1_rl1_w128_exactphase_base_20260615
DEDUP_T1=$SCR/fullsys_flowstats_exactphase/dedup_c16_l2256kB_d4_mc1_T1_inter25_ll1_rl1_w128_exactphase_self_20260615

DEDUP_T1_TRUTH=$SCR/fullsys_flowstats_fullroi/dedup_c16_l2256kB_d4_mc1_T1_inter25_w128_componentjointprof_fullroi_20260615/pace_profiler_extra.json
CANNEAL_T1_TRUTH=$SCR/fullsys_flowstats_fullroi/canneal_c16_l2256kB_d4_mc1_T1_inter25_w128_componentjointprof_fullroi_20260615/pace_profiler_extra.json
BLACKSCHOLES_T1_TRUTH=$SCR/fullsys_flowstats_fullroi/blackscholes_c16_l2256kB_d4_mc1_T1_inter25_w128_componentjointprof_fullroi_20260614/pace_profiler_extra.json

require_file() {
  if [ ! -s "$1" ]; then
    echo "missing required file: $1" >&2
    exit 2
  fi
}

validate_profile() {
  local label=$1
  local run_dir=$2
  require_file "$run_dir/pace_profiler_extra.json"
  require_file "$run_dir/component_traffic_profile.json"
  python3 - "$label" "$run_dir/pace_profiler_extra.json" "$run_dir/component_traffic_profile.json" <<'PY'
import json
import sys

label, extra_path, profile_path = sys.argv[1:]
extra = json.load(open(extra_path))
profile = json.load(open(profile_path))
extra_rows = extra.get("phase_src_dst_ni_flits_counts_by_vnet", [])
profile_rows = [
    phase for phase in profile.get("phases", [])
    if phase.get("src_dst_ni_flits_counts_by_vnet")
]
print(
    f"{label}: exact_extra_phases={len(extra_rows)} "
    f"exact_profile_phases={len(profile_rows)} "
    f"avg={extra.get('avg_packet_latency_cycles')} "
    f"p99={extra.get('p99_packet_latency_cycles')}"
)
if not extra_rows:
    raise SystemExit(f"{label}: missing exact phase endpoint counts in extra json")
if not profile_rows:
    raise SystemExit(f"{label}: missing exact phase endpoint counts in profile")
PY
}

mkdir -p "$EVAL"

cd "$WT"
validate_profile dedup_T0 "$DEDUP_T0"
validate_profile canneal_T0 "$CANNEAL_T0"
validate_profile blackscholes_T0 "$BLACKSCHOLES_T0"
validate_profile dedup_T1 "$DEDUP_T1"

require_file "$TOPO_T1"
require_file "$DEDUP_T1_TRUTH"
require_file "$CANNEAL_T1_TRUTH"
require_file "$BLACKSCHOLES_T1_TRUTH"

python3 tools/run_transfer_matrix.py \
  --pace-bin ./pace-new \
  --cwd "$WT" \
  --output-dir "$EVAL" \
  --summary "$EVAL/summary_exactphase_transfer_20260615.csv" \
  --case "dedup_T0exact_to_T1inter25:$TOPO_T1:$DEDUP_T0/component_traffic_profile.json:$DEDUP_T1_TRUTH" \
  --case "canneal_T0exact_to_T1inter25:$TOPO_T1:$CANNEAL_T0/component_traffic_profile.json:$CANNEAL_T1_TRUTH" \
  --case "blackscholes_T0exact_to_T1inter25:$TOPO_T1:$BLACKSCHOLES_T0/component_traffic_profile.json:$BLACKSCHOLES_T1_TRUTH" \
  --case "dedup_T1exact_self:$TOPO_T1:$DEDUP_T1/component_traffic_profile.json:$DEDUP_T1/pace_profiler_extra.json"

cat "$EVAL/summary_exactphase_transfer_20260615.csv"
