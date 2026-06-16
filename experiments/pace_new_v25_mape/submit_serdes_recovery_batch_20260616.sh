#!/bin/bash
set -eo pipefail

EXP=/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606
SCR=/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606
RUNNER=$EXP/scripts/run_fullsys_exactphase_one.sh
TAG=${TAG:-exactphase_serdes_recovery_20260616c}
MANIFEST=$SCR/fullsys_flowstats_exactphase/${TAG}_manifest.csv
JOBLIST=$SCR/fullsys_flowstats_exactphase/${TAG}_jobs.txt
SOURCE_MANIFESTS=(
  "$SCR/fullsys_flowstats_exactphase/exactphase_hugebatch_20260616a_manifest.csv"
  "$SCR/fullsys_flowstats_exactphase/exactphase_megabatch_20260616b_manifest.csv"
)

mkdir -p "$(dirname "$MANIFEST")"
echo "job_id,bench,topo_id,topo_label,num_cpus,num_dirs,l2_size,mem_channels,parsec_input,link_latency,router_latency,link_width_bits,inter_latency,inter_width,tag,group,source_job_id,source_tag" > "$MANIFEST"
: > "$JOBLIST"

submit_source_row() {
  local src_job_id=$1
  local bench=$2
  local topo_id=$3
  local topo_label=$4
  local num_cpus=$5
  local num_dirs=$6
  local l2_size=$7
  local mem_channels=$8
  local parsec_input=$9
  local link_latency=${10}
  local router_latency=${11}
  local link_width_bits=${12}
  local inter_latency=${13}
  local inter_width=${14}
  local source_tag=${15}
  local group=${16}

  local out
  out=$(sbatch --parsable \
    --export=ALL,BENCH="$bench",TOPO_ID="$topo_id",TOPO_LABEL="$topo_label",NUM_CPUS="$num_cpus",NUM_DIRS="$num_dirs",L2_SIZE="$l2_size",MEM_CHANNELS="$mem_channels",PARSEC_INPUT="$parsec_input",LINK_LATENCY="$link_latency",ROUTER_LATENCY="$router_latency",LINK_WIDTH_BITS="$link_width_bits",INTER_LATENCY="$inter_latency",INTER_WIDTH="$inter_width",TAG="$TAG" \
    "$RUNNER")
  local job_id=${out%%;*}
  echo "$job_id" >> "$JOBLIST"
  echo "$job_id,$bench,$topo_id,$topo_label,$num_cpus,$num_dirs,$l2_size,$mem_channels,$parsec_input,$link_latency,$router_latency,$link_width_bits,$inter_latency,$inter_width,$TAG,$group,$src_job_id,$source_tag" >> "$MANIFEST"
  echo "submitted $job_id recovery $bench $topo_label from=$src_job_id"
}

while IFS=, read -r job_id bench topo_id topo_label num_cpus num_dirs l2_size mem_channels parsec_input link_latency router_latency link_width_bits inter_latency inter_width source_tag group; do
  [[ "$job_id" == "job_id" || -z "$job_id" ]] && continue
  if [[ "$topo_id" == "T5" ]] || { [[ "$group" == "chiplet_width" || "$group" == "chiplet_inter_width" ]] && [[ "$inter_width" != "128" ]]; }; then
    submit_source_row "$job_id" "$bench" "$topo_id" "$topo_label" "$num_cpus" "$num_dirs" "$l2_size" "$mem_channels" "$parsec_input" "$link_latency" "$router_latency" "$link_width_bits" "$inter_latency" "$inter_width" "$source_tag" "$group"
  fi
done < <(cat "${SOURCE_MANIFESTS[@]}")

echo "manifest=$MANIFEST"
echo "jobs=$JOBLIST"
