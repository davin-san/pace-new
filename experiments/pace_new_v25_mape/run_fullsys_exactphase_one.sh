#!/bin/bash
#SBATCH --job-name=fs-exactphase
#SBATCH --account=gts-chao33
#SBATCH --partition=cpu-small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/logs/fs-exactphase_%j.out
#SBATCH --error=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/logs/fs-exactphase_%j.err

set -eo pipefail

if [ ! -e /dev/kvm ]; then
  echo "no /dev/kvm on node"
  exit 42
fi

module load anaconda3
source activate gem5_env
export LD_LIBRARY_PATH=/storage/home/hcoda1/9/daoyama3/.conda/envs/gem5_env/lib

EXP=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606
SCR=/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606
GEM5=$SCR/gem5_profiler_build/gem5/build/X86_MESI_Two_Level/gem5.opt
GEM5_DIR=$SCR/gem5_profiler_build/gem5
SIM=$EXP/scripts/pace_sim_v25_mesh_params.py
PARSER=$EXP/scripts/pace_parse_v25.py
BUILDER=$EXP/scripts/build_component_traffic_profile.py

BENCH=${BENCH:-dedup}
TOPO_ID=${TOPO_ID:-T1}
TOPO_LABEL=${TOPO_LABEL:-T1_inter25}
INTER_LATENCY=${INTER_LATENCY:-25}
INTER_WIDTH=${INTER_WIDTH:-128}
LINK_LATENCY=${LINK_LATENCY:-1}
ROUTER_LATENCY=${ROUTER_LATENCY:-1}
LINK_WIDTH_BITS=${LINK_WIDTH_BITS:-128}
NUM_CPUS=${NUM_CPUS:-16}
NUM_DIRS=${NUM_DIRS:-4}
L2_SIZE=${L2_SIZE:-256kB}
MEM_CHANNELS=${MEM_CHANNELS:-1}
PARSEC_INPUT=${PARSEC_INPUT:-simsmall}
PHASE_WINDOWS=${PHASE_WINDOWS:-80}
PHASE_TICKS=${PHASE_TICKS:-400000000}
TAG=${TAG:-exactphase_20260615}

OUT=$SCR/fullsys_flowstats_exactphase/${BENCH}_c${NUM_CPUS}_l2${L2_SIZE}_d${NUM_DIRS}_mc${MEM_CHANNELS}_${TOPO_LABEL}_ll${LINK_LATENCY}_rl${ROUTER_LATENCY}_w${LINK_WIDTH_BITS}_${TAG}
mkdir -p "$OUT"

echo "node=$(hostname) kvm=ok out=$OUT"
cd "$GEM5_DIR"

GEM5_ARGS=(
  -d "$OUT" "$SIM"
  --topo-id "$TOPO_ID"
  --benchmark "$BENCH"
  --num-cpus "$NUM_CPUS"
  --num-dirs "$NUM_DIRS"
  --l2size "$L2_SIZE"
  --mem-channels "$MEM_CHANNELS"
  --parsec-input "$PARSEC_INPUT"
  --phase-windows "$PHASE_WINDOWS"
  --phase-ticks "$PHASE_TICKS"
  --link-latency "$LINK_LATENCY"
  --router-latency "$ROUTER_LATENCY"
  --link-width-bits "$LINK_WIDTH_BITS"
)

if [ "$TOPO_ID" != "T0" ]; then
  GEM5_ARGS+=(--inter-latency "$INTER_LATENCY" --inter-width "$INTER_WIDTH")
fi

"$GEM5" "${GEM5_ARGS[@]}"
python3 "$PARSER" --run-dir "$OUT" --output-csv "$OUT/profile.csv"
python3 "$BUILDER" \
  --profile "$OUT/pace_profile.json" \
  --extra "$OUT/pace_profiler_extra.json" \
  --output "$OUT/component_traffic_profile.json"

echo "wrote $OUT"
