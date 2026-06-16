#!/bin/bash
set -eo pipefail

EXP=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606
SCR=/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606
RUNNER=$EXP/scripts/run_fullsys_exactphase_one.sh
TAG=${TAG:-exactphase_hugebatch_20260616a}
MANIFEST=$SCR/fullsys_flowstats_exactphase/${TAG}_manifest.csv
JOBLIST=$SCR/fullsys_flowstats_exactphase/${TAG}_jobs.txt

mkdir -p "$(dirname "$MANIFEST")"
echo "job_id,bench,topo_id,topo_label,num_cpus,num_dirs,l2_size,mem_channels,parsec_input,link_latency,router_latency,link_width_bits,inter_latency,inter_width,tag,group" > "$MANIFEST"
: > "$JOBLIST"

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

  local out
  out=$(sbatch --parsable \
    --export=ALL,BENCH="$bench",TOPO_ID="$topo_id",TOPO_LABEL="$topo_label",NUM_CPUS="$num_cpus",NUM_DIRS="$num_dirs",L2_SIZE="$l2_size",MEM_CHANNELS="$mem_channels",PARSEC_INPUT="$parsec_input",LINK_LATENCY="$link_latency",ROUTER_LATENCY="$router_latency",LINK_WIDTH_BITS="$link_width_bits",INTER_LATENCY="$inter_latency",INTER_WIDTH="$inter_width",TAG="$TAG" \
    "$RUNNER")
  local job_id=${out%%;*}
  echo "$job_id" >> "$JOBLIST"
  echo "$job_id,$bench,$topo_id,$topo_label,$num_cpus,$num_dirs,$l2_size,$mem_channels,$parsec_input,$link_latency,$router_latency,$link_width_bits,$inter_latency,$inter_width,$TAG,$group" >> "$MANIFEST"
  echo "submitted $job_id $bench $topo_label $group"
}

known_workloads=(blackscholes canneal dedup)

for bench in "${known_workloads[@]}"; do
  submit_case "$bench" T0 T0_mesh topo_baseline
  submit_case "$bench" T0 T0_mesh_ll2 t0_link_latency 16 4 256kB 1 simsmall 2 1 128
  submit_case "$bench" T0 T0_mesh_ll3 t0_link_latency 16 4 256kB 1 simsmall 3 1 128
  submit_case "$bench" T0 T0_mesh_rl2 t0_router_latency 16 4 256kB 1 simsmall 1 2 128
  submit_case "$bench" T0 T0_mesh_ll2_rl2 t0_link_router_latency 16 4 256kB 1 simsmall 2 2 128
  submit_case "$bench" T0 T0_mesh_w64 t0_width 16 4 256kB 1 simsmall 1 1 64
  submit_case "$bench" T0 T0_mesh_w256 t0_width 16 4 256kB 1 simsmall 1 1 256

  submit_case "$bench" T1_base T1_base chiplet_structure 16 4 256kB 1 simsmall 1 1 128 1 128
  submit_case "$bench" T1 T1_inter5 chiplet_inter_latency 16 4 256kB 1 simsmall 1 1 128 5 128
  submit_case "$bench" T1 T1_inter10 chiplet_inter_latency 16 4 256kB 1 simsmall 1 1 128 10 128
  submit_case "$bench" T1 T1_inter25 chiplet_inter_latency 16 4 256kB 1 simsmall 1 1 128 25 128
  submit_case "$bench" T1 T1_inter50 chiplet_inter_latency 16 4 256kB 1 simsmall 1 1 128 50 128
  submit_case "$bench" T1 T1_inter25_iw64 chiplet_inter_width 16 4 256kB 1 simsmall 1 1 128 25 64
  submit_case "$bench" T1 T1_inter25_iw256 chiplet_inter_width 16 4 256kB 1 simsmall 1 1 128 25 256
  submit_case "$bench" T2 T2_mesh_inter25 chiplet_topology 16 4 256kB 1 simsmall 1 1 128 25 128
  submit_case "$bench" T3 T3_fc_inter25 chiplet_topology 16 4 256kB 1 simsmall 1 1 128 25 128
  submit_case "$bench" T4 T4_bus_inter25 chiplet_topology 16 4 256kB 1 simsmall 1 1 128 25 128
  submit_case "$bench" T5 T5_cmesh_ring25 chiplet_shape 16 4 256kB 1 simsmall 1 1 128 25 128
  submit_case "$bench" T6 T6_rect_ring25 chiplet_shape 16 4 256kB 1 simsmall 1 1 128 25 128

  submit_case "$bench" T0 T0_mesh_c8_d2 arch_factor 8 2 256kB 1 simsmall 1 1 128
  submit_case "$bench" T0 T0_mesh_c32_d8 arch_factor 32 8 256kB 1 simsmall 1 1 128
  submit_case "$bench" T0 T0_mesh_l2512kB arch_factor 16 4 512kB 1 simsmall 1 1 128
  submit_case "$bench" T0 T0_mesh_mc2 arch_factor 16 4 256kB 2 simsmall 1 1 128
done

# Isolated workload-discovery strip. These are intentionally T0 baseline only:
# they expand workload coverage without multiplying failures across topologies.
candidate_workloads=(bodytrack facesim ferret fluidanimate freqmine raytrace streamcluster swaptions vips x264)
for bench in "${candidate_workloads[@]}"; do
  submit_case "$bench" T0 T0_mesh workload_probe 16 4 256kB 1 simsmall 1 1 128
done

echo "manifest=$MANIFEST"
echo "jobs=$JOBLIST"
