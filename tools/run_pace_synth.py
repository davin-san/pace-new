#!/usr/bin/env python3
"""Run pace-new Garnet synthetic trials and write canonical stats artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def generator_args(trial: dict[str, object], output: Path) -> list[str]:
    args = [
        "--num-cpus", str(trial["num_cpus"]),
        "--num-dirs", str(trial["num_dirs"]),
        "--network", "garnet",
        "--topology", str(trial["topology"]),
        "--mesh-rows", str(trial.get("mesh_rows", 0)),
        "--sim-cycles", str(trial["sim_cycles"]),
        "--synthetic", str(trial["synthetic"]),
        "--injectionrate", str(trial["injectionrate"]),
        "--num-packets-max", str(trial["num_packets_max"]),
        "--inj-vnet", str(trial.get("inj_vnet", -1)),
        "--seed", str(trial.get("seed", 1)),
        "--output", str(output),
    ]
    if "single_sender_id" in trial:
        args += ["--single-sender-id", str(trial["single_sender_id"])]
    if "single_dest_id" in trial:
        args += ["--single-dest-id", str(trial["single_dest_id"])]
    if "chiplet_spec" in trial:
        args += ["--chiplet-spec", str(trial["chiplet_spec"])]
    return args


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trials",
        type=Path,
        default=Path("verif/trials/garnet_synth_smoke.json"),
    )
    parser.add_argument("--outdir", type=Path, default=Path("verif/out/pace"))
    parser.add_argument("--drain-cycles", type=int, default=500)
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    generator = root / "configs" / "example" / "garnet_synth_traffic.py"
    binary = root / "pace-new"
    if not binary.exists():
        raise SystemExit("pace-new executable is missing; run make all first")

    trials = json.loads(args.trials.read_text())
    args.outdir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for trial in trials:
        name = str(trial["name"])
        trial_out = args.outdir / name
        trial_out.mkdir(parents=True, exist_ok=True)
        topology_json = trial_out / "topology.json"
        stats_json = trial_out / "stats.json"
        trace_jsonl = trial_out / "trace.jsonl"
        log_path = trial_out / "stdout.log"

        print(f"[pace] {name}")
        gen = subprocess.run(
            [sys.executable, str(generator), *generator_args(trial, topology_json)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if gen.returncode != 0:
            failures += 1
            log_path.write_text(gen.stdout)
            print(f"  FAIL topology rc={gen.returncode} log={log_path}")
            continue

        run_cmd = [
            str(binary),
            "--topology-json", str(topology_json),
            "--simulate",
            "--drain-cycles", str(args.drain_cycles),
            "--stats-json", str(stats_json),
        ]
        if args.trace:
            run_cmd += ["--trace-jsonl", str(trace_jsonl)]

        proc = subprocess.run(
            run_cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        log_path.write_text(proc.stdout)
        if proc.returncode != 0:
            failures += 1
            print(f"  FAIL rc={proc.returncode} log={log_path}")
        else:
            stats = json.loads(stats_json.read_text())
            delivered = stats["traffic"]["delivered_packets"]
            print(f"  PASS delivered={delivered} stats={stats_json}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
