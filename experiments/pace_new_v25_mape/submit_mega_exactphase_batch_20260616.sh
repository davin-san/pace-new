#!/bin/bash
set -eo pipefail

EXP=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606
SCR=/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606
RUNNER=$EXP/scripts/run_fullsys_exactphase_one.sh
TAG=${TAG:-exactphase_megabatch_20260616b}
MANIFEST=$SCR/fullsys_flowstats_exactphase/${TAG}_manifest.csv
JOBLIST=$SCR/fullsys_flowstats_exactphase/${TAG}_jobs.txt
LIMIT=${LIMIT:-0}
SUBMIT_DELAY_SEC=${SUBMIT_DELAY_SEC:-0}
APPEND=${APPEND:-0}

mkdir -p "$(dirname "$MANIFEST")"
if (( APPEND == 1 )) && [[ -f "$MANIFEST" && -f "$JOBLIST" ]]; then
  echo "resuming manifest=$MANIFEST jobs=$JOBLIST"
else
  echo "job_id,bench,topo_id,topo_label,num_cpus,num_dirs,l2_size,mem_channels,parsec_input,link_latency,router_latency,link_width_bits,inter_latency,inter_width,tag,group" > "$MANIFEST"
  : > "$JOBLIST"
fi

declare -A SEEN
SUBMITTED=0
SKIPPED_INVALID=0

if [[ -f "$MANIFEST" ]]; then
  while IFS=, read -r job_id bench topo_id topo_label num_cpus num_dirs l2_size mem_channels parsec_input link_latency router_latency link_width_bits inter_latency inter_width tag group; do
    [[ "$job_id" == "job_id" || -z "$job_id" ]] && continue
    key="$bench,$topo_id,$topo_label,$num_cpus,$num_dirs,$l2_size,$mem_channels,$parsec_input,$link_latency,$router_latency,$link_width_bits,$inter_latency,$inter_width"
    SEEN[$key]=1
  done < "$MANIFEST"
fi

skip_invalid_case() {
  local topo_id=$1
  local group=$2
  local inter_width=$3

  # PACE_Chiplet_CMesh currently fails before simulation because its topology
  # module cannot import PACE_Chiplet in the profiler gem5 tree.
  if [[ "$topo_id" == "T5" ]]; then
    return 0
  fi

  # gem5 Garnet rejects heterogeneous link/router widths without SerDes.
  if [[ "$group" == "chiplet_width" || "$group" == "chiplet_inter_width" ]] && [[ "$inter_width" != "128" ]]; then
    return 0
  fi

  return 1
}

submit_case() {
  local bench=$1
  local topo_id=$2
  local topo_label=$3
  local group=$4
  local num_cpus=${5:-16}
  local num_dirs=${6:-4}
  local l2_size=${7:-256kB}
  local mem_channels=${8:-1}
  local parsec_input=${9:-simsmall}
  local link_latency=${10:-1}
  local router_latency=${11:-1}
  local link_width_bits=${12:-128}
  local inter_latency=${13:-25}
  local inter_width=${14:-128}

  if skip_invalid_case "$topo_id" "$group" "$inter_width"; then
    SKIPPED_INVALID=$((SKIPPED_INVALID + 1))
    return 0
  fi

  local key="$bench,$topo_id,$topo_label,$num_cpus,$num_dirs,$l2_size,$mem_channels,$parsec_input,$link_latency,$router_latency,$link_width_bits,$inter_latency,$inter_width"
  if [[ -n "${SEEN[$key]:-}" ]]; then
    return 0
  fi
  SEEN[$key]=1

  if (( LIMIT > 0 && SUBMITTED >= LIMIT )); then
    return 0
  fi

  local out
  out=$(sbatch --parsable \
    --export=ALL,BENCH="$bench",TOPO_ID="$topo_id",TOPO_LABEL="$topo_label",NUM_CPUS="$num_cpus",NUM_DIRS="$num_dirs",L2_SIZE="$l2_size",MEM_CHANNELS="$mem_channels",PARSEC_INPUT="$parsec_input",LINK_LATENCY="$link_latency",ROUTER_LATENCY="$router_latency",LINK_WIDTH_BITS="$link_width_bits",INTER_LATENCY="$inter_latency",INTER_WIDTH="$inter_width",TAG="$TAG" \
    "$RUNNER")
  local job_id=${out%%;*}
  echo "$job_id" >> "$JOBLIST"
  echo "$job_id,$bench,$topo_id,$topo_label,$num_cpus,$num_dirs,$l2_size,$mem_channels,$parsec_input,$link_latency,$router_latency,$link_width_bits,$inter_latency,$inter_width,$TAG,$group" >> "$MANIFEST"
  SUBMITTED=$((SUBMITTED + 1))
  echo "submitted $job_id $bench $topo_label $group"

  if (( SUBMIT_DELAY_SEC > 0 )); then
    sleep "$SUBMIT_DELAY_SEC"
  fi
}

known_workloads=(blackscholes canneal dedup)
candidate_workloads=(bodytrack facesim ferret fluidanimate freqmine raytrace streamcluster swaptions vips x264)

# Flat-mesh network factors. This is the extraction-domain stress set: it
# isolates Garnet link latency, router latency, and serialization width without
# changing workload or cache/memory factors.
for bench in "${known_workloads[@]}"; do
  for link_latency in 1 2 3 4 8; do
    for router_latency in 1 2 4; do
      for width in 32 64 128 256; do
        submit_case "$bench" T0 "T0_mesh_ll${link_latency}_rl${router_latency}_w${width}" \
          flat_mesh_factorial 16 4 256kB 1 simsmall \
          "$link_latency" "$router_latency" "$width" 25 128
      done
    done
  done
done

# Chiplet topology and interconnect factors for the validated workloads. These
# are the target domains that should eventually be predicted from simple-mesh
# traffic profiles.
for bench in "${known_workloads[@]}"; do
  submit_case "$bench" T1_base T1_base chiplet_base 16 4 256kB 1 simsmall 1 1 128 1 128

  for topo_id in T1 T2 T3 T4 T5 T6; do
    for inter_latency in 2 5 10 25 50 100; do
      submit_case "$bench" "$topo_id" "${topo_id}_inter${inter_latency}_w128" \
        chiplet_latency 16 4 256kB 1 simsmall 1 1 128 "$inter_latency" 128
    done
    for inter_width in 32 64 128 256 512; do
      submit_case "$bench" "$topo_id" "${topo_id}_inter25_iw${inter_width}" \
        chiplet_width 16 4 256kB 1 simsmall 1 1 128 25 "$inter_width"
    done
  done

  for topo_id in T1_8c T2_8c; do
    for inter_latency in 5 25 50; do
      submit_case "$bench" "$topo_id" "${topo_id}_inter${inter_latency}_w128" \
        chiplet_8c 64 8 256kB 1 simsmall 1 1 128 "$inter_latency" 128
    done
  done
done

# Architecture factors on the extraction mesh. These runs tell us whether a
# single traffic profile remains reusable after changing non-network factors.
for bench in "${known_workloads[@]}"; do
  for combo in \
    "4 1" "4 2" \
    "8 1" "8 2" "8 4" \
    "16 1" "16 2" "16 4" "16 8" \
    "32 4" "32 8" "32 16"; do
    set -- $combo
    submit_case "$bench" T0 "T0_arch_c${1}_d${2}" \
      arch_cpu_dir "$1" "$2" 256kB 1 simsmall 1 1 128 25 128
  done

  for l2_size in 128kB 512kB 1MB 2MB; do
    submit_case "$bench" T0 "T0_arch_l2${l2_size}" \
      arch_l2 16 4 "$l2_size" 1 simsmall 1 1 128 25 128
  done

  for mem_channels in 1 2 4; do
    submit_case "$bench" T0 "T0_arch_mc${mem_channels}" \
      arch_mem_channels 16 4 256kB "$mem_channels" simsmall 1 1 128 25 128
  done
done

# Broad workload strip. These jobs are intentionally shallower per workload:
# they identify which PARSEC apps run cleanly and whether the current traffic
# profile transfer generalizes beyond the three validated workloads.
for bench in "${candidate_workloads[@]}"; do
  submit_case "$bench" T0 T0_mesh workload_t0 16 4 256kB 1 simsmall 1 1 128 25 128
  submit_case "$bench" T0 T0_mesh_ll2 workload_t0_latency 16 4 256kB 1 simsmall 2 1 128 25 128
  submit_case "$bench" T0 T0_mesh_rl2 workload_t0_latency 16 4 256kB 1 simsmall 1 2 128 25 128
  submit_case "$bench" T0 T0_mesh_w64 workload_t0_width 16 4 256kB 1 simsmall 1 1 64 25 128
  submit_case "$bench" T1_base T1_base workload_chiplet 16 4 256kB 1 simsmall 1 1 128 1 128
  submit_case "$bench" T1 T1_inter25 workload_chiplet 16 4 256kB 1 simsmall 1 1 128 25 128
  submit_case "$bench" T2 T2_inter25 workload_chiplet 16 4 256kB 1 simsmall 1 1 128 25 128
  submit_case "$bench" T5 T5_inter25 workload_chiplet_shape 16 4 256kB 1 simsmall 1 1 128 25 128
  submit_case "$bench" T6 T6_inter25 workload_chiplet_shape 16 4 256kB 1 simsmall 1 1 128 25 128
done

echo "submitted=$SUBMITTED"
echo "skipped_invalid=$SKIPPED_INVALID"
echo "manifest=$MANIFEST"
echo "jobs=$JOBLIST"
