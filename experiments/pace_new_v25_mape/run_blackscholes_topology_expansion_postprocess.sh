#!/bin/bash
#SBATCH --job-name=bs-topo-post
#SBATCH --account=gts-chao33
#SBATCH --partition=cpu-small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/logs/bs-topo-post_%j.out
#SBATCH --error=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/logs/bs-topo-post_%j.err

set -eo pipefail

SCR=/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606
WT=$SCR/pace_new_worktrees/phase_condition_20260615
EVAL=$SCR/pace_flowtiming_eval/exactphase_blackscholes_topology_targets_20260615

SOURCE=$SCR/fullsys_flowstats_exactphase/blackscholes_c16_l2256kB_d4_mc1_T0_mesh_ll1_rl1_w128_exactphase_base_envfix_20260615
T0_LL2=$SCR/fullsys_flowstats_exactphase/blackscholes_c16_l2256kB_d4_mc1_T0_mesh_ll2_ll2_rl1_w128_exactphase_target_envfix_20260615
T0_W256=$SCR/fullsys_flowstats_exactphase/blackscholes_c16_l2256kB_d4_mc1_T0_mesh_w256_ll1_rl1_w256_exactphase_target_envfix_20260615
T1_BASE=$SCR/fullsys_flowstats_exactphase/blackscholes_c16_l2256kB_d4_mc1_T1_base_ll1_rl1_w128_exactphase_target_envfix_20260615
T1_RING25=$SCR/fullsys_flowstats_exactphase/blackscholes_c16_l2256kB_d4_mc1_T1_inter25_ll1_rl1_w128_exactphase_target_envfix_20260615

TOPO_T0_BASE=$SCR/next_phase_pace_sweep/blackscholes_componentjoint_topology_latency_metadata_20260607/baseline/topology.json
TOPO_T0_LL2=$SCR/next_phase_pace_sweep/blackscholes_componentjoint_topology_latency_metadata_20260607/int_lat2/topology.json
TOPO_T0_W256=$SCR/generated_topologies/blackscholes_meshxy_w256.json
TOPO_T1_BASE=$SCR/generated_topologies/blackscholes_t1_base_chiplet.json
TOPO_T1_RING25=$SCR/generated_topologies/blackscholes_t1_ring_lat25_chiplet.json

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
    f"packets={extra.get('total_pkts_profiled')} "
    f"avg={extra.get('avg_packet_latency_cycles')} "
    f"p99={extra.get('p99_packet_latency_cycles')}"
)
if not extra_rows or not profile_rows:
    raise SystemExit(f"{label}: missing exact phase endpoint counts")
PY
}

mkdir -p "$EVAL"
cd "$WT"

validate_profile source_T0 "$SOURCE"
validate_profile target_T0_ll2 "$T0_LL2"
validate_profile target_T0_w256 "$T0_W256"
validate_profile target_T1_base "$T1_BASE"
validate_profile target_T1_ring25 "$T1_RING25"

python3 tools/run_transfer_matrix.py \
  --pace-bin "$WT/pace-new" \
  --cwd "$WT" \
  --output-dir "$EVAL" \
  --summary "$EVAL/summary_blackscholes_exact_topology_targets_20260615.csv" \
  --case "blackscholes_T0exact_self:$TOPO_T0_BASE:$SOURCE/component_traffic_profile.json:$SOURCE/pace_profiler_extra.json" \
  --case "blackscholes_T0exact_to_T0_ll2:$TOPO_T0_LL2:$SOURCE/component_traffic_profile.json:$T0_LL2/pace_profiler_extra.json" \
  --case "blackscholes_T0exact_to_T0_w256:$TOPO_T0_W256:$SOURCE/component_traffic_profile.json:$T0_W256/pace_profiler_extra.json" \
  --case "blackscholes_T0exact_to_T1base:$TOPO_T1_BASE:$SOURCE/component_traffic_profile.json:$T1_BASE/pace_profiler_extra.json" \
  --case "blackscholes_T0exact_to_T1ring25:$TOPO_T1_RING25:$SOURCE/component_traffic_profile.json:$T1_RING25/pace_profiler_extra.json"

cat "$EVAL/summary_blackscholes_exact_topology_targets_20260615.csv"
