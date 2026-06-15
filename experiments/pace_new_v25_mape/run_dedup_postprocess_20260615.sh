#!/bin/bash
#SBATCH --job-name=dedup-post
#SBATCH --account=gts-chao33
#SBATCH --partition=cpu-small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/logs/dedup-post_%j.out
#SBATCH --error=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/logs/dedup-post_%j.err

set -euo pipefail

REPO=/storage/home/hcoda1/9/daoyama3/r-chao33-0/pace-new
SCRATCH=/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606
FULL=$SCRATCH/fullsys_flowstats_fullroi
OUT=$SCRATCH/pace_flowtiming_eval/dedup_fullroi_transfer_20260615

BASE_DIR=$FULL/dedup_c16_l2256kB_d4_mc1_T0_mesh_ll1_rl1_w128_componentjointprof_fullroi_20260615
TARGET_DIR=$FULL/dedup_c16_l2256kB_d4_mc1_T1_inter25_w128_componentjointprof_fullroi_20260615
TOPOLOGY=$SCRATCH/pace_flowtiming_eval/blackscholes_t1_inter25_20260609/topology.json

BASE_PROFILE=$BASE_DIR/component_traffic_profile.json
TARGET_PROFILE=$TARGET_DIR/component_traffic_profile.json
BASE_EXTRA=$BASE_DIR/pace_profiler_extra.json
TARGET_EXTRA=$TARGET_DIR/pace_profiler_extra.json

mkdir -p "$OUT"
cd "$REPO"

for f in "$BASE_PROFILE" "$TARGET_PROFILE" "$BASE_EXTRA" "$TARGET_EXTRA" "$TOPOLOGY"; do
  test -s "$f" || { echo "missing required file: $f" >&2; exit 2; }
done

echo "dedup postprocess node=$(hostname) out=$OUT"

python3 tools/demand_throttle_model.py \
  --baseline-profile "$BASE_PROFILE" \
  --baseline-extra "$BASE_EXTRA" \
  --target-extra "$TARGET_EXTRA" \
  --target-profile "$TARGET_PROFILE" \
  --label dedup_T0_to_T1inter25 \
  > "$OUT/demand_throttle_model_dedup_T0_to_T1inter25_20260615.csv"

python3 tools/profile_mix_report.py \
  "$BASE_PROFILE" "$TARGET_PROFILE" \
  --labels dedup_T0,dedup_T1inter25 \
  > "$OUT/profile_mix_dedup_t0_vs_t1inter25_20260615.csv"

./pace-new \
  --topology-json "$TOPOLOGY" \
  --simulate \
  --traffic-profile-json "$TARGET_PROFILE" \
  --profile-phased \
  --profile-flow-timing-auto \
  --drain-cycles 20000 \
  --stats-json "$OUT/stats_dedup_t1inter25_self_auto_sparsegate.json"

python3 tools/latency_mape_report.py \
  --case "dedup_t1_self:$TARGET_EXTRA:$OUT/stats_dedup_t1inter25_self_auto_sparsegate.json" \
  --output "$OUT/summary_dedup_self_20260615.csv"

PRED_TARGET_PACKETS=$(python3 -c '
import sys
from pathlib import Path
sys.path.insert(0, "tools")
import demand_throttle_model as model
base_profile = model._load_profile(Path(sys.argv[1]))
base_extra = model._load_extra(Path(sys.argv[2]))
target_extra = model._load_extra(Path(sys.argv[3]))
base_latency = float(base_extra.get("avg_packet_latency_cycles", 0.0) or 0.0)
target_latency = float(target_extra.get("avg_packet_latency_cycles", 0.0) or 0.0)
ratio, *_ = model.predict_ratio(base_profile, base_latency, target_latency)
packets = float(base_profile.get("scale", {}).get("total_packets", 0) or 0)
print(max(1, int(round(ratio * packets))))
' "$BASE_PROFILE" "$BASE_EXTRA" "$TARGET_EXTRA")

BASE_SIM_CYCLES=$(python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); print(int(p.get("scale", {}).get("sim_cycles", 0) or 0))' "$BASE_PROFILE")
BASE_LAMBDA=$(python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); print(float(p.get("scale", {}).get("lambda_per_cpu", 0.0) or 0.0))' "$BASE_PROFILE")
BASE_PACKETS=$(python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); print(int(p.get("scale", {}).get("total_packets", 0) or 0))' "$BASE_PROFILE")
PRED_LAMBDA=$(python3 -c 'import sys; base_lambda=float(sys.argv[1]); pred=float(sys.argv[2]); base=float(sys.argv[3]); print(base_lambda * pred / base if base > 0 else 0.0)' "$BASE_LAMBDA" "$PRED_TARGET_PACKETS" "$BASE_PACKETS")

SCALED_PROFILE=$OUT/dedup_t0_profile_scaled_by_predicted_feedback.json
python3 tools/profile_scale_counts.py \
  --input "$BASE_PROFILE" \
  --output "$SCALED_PROFILE" \
  --target-packets "$PRED_TARGET_PACKETS" \
  --sim-cycles "$BASE_SIM_CYCLES" \
  --lambda-per-cpu "$PRED_LAMBDA"

./pace-new \
  --topology-json "$TOPOLOGY" \
  --simulate \
  --traffic-profile-json "$SCALED_PROFILE" \
  --profile-phased \
  --profile-flow-timing-auto \
  --drain-cycles 20000 \
  --stats-json "$OUT/stats_dedup_t0_predscaled_to_t1inter25_auto_sparsegate.json"

python3 tools/latency_mape_report.py \
  --case "dedup_t1_self:$TARGET_EXTRA:$OUT/stats_dedup_t1inter25_self_auto_sparsegate.json" \
  --case "dedup_t0_predscaled_t1:$TARGET_EXTRA:$OUT/stats_dedup_t0_predscaled_to_t1inter25_auto_sparsegate.json" \
  --output "$OUT/summary_dedup_self_and_predscaled_20260615.csv"

echo "wrote:"
ls -1 "$OUT"
