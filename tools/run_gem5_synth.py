#!/usr/bin/env python3
"""Run gem5 Garnet_standalone synthetic trials from the compiled Docker volume."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


DEFAULT_IMAGE = "unified-framework-init-builder:latest"
DEFAULT_GEM5_VOLUME = "unified-framework_gem5-source"


def trial_args(trial: dict[str, object]) -> list[str]:
    args = [
        "--num-cpus", str(trial["num_cpus"]),
        "--num-dirs", str(trial["num_dirs"]),
        "--network", "garnet",
        "--topology", str(trial["topology"]),
        "--mesh-rows", str(trial["mesh_rows"]),
        "--sim-cycles", str(trial["sim_cycles"]),
        "--synthetic", str(trial["synthetic"]),
        "--injectionrate", str(trial["injectionrate"]),
        "--num-packets-max", str(trial["num_packets_max"]),
        "--inj-vnet", str(trial.get("inj_vnet", -1)),
    ]
    if "single_sender_id" in trial:
        args += ["--single-sender-id", str(trial["single_sender_id"])]
    if "single_dest_id" in trial:
        args += ["--single-dest-id", str(trial["single_dest_id"])]
    return args


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trials",
        type=Path,
        default=Path("verif/trials/garnet_synth_smoke.json"),
    )
    parser.add_argument("--outdir", type=Path, default=Path("verif/out/gem5"))
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--gem5-volume", default=DEFAULT_GEM5_VOLUME)
    parser.add_argument("--gem5-root", type=Path, default=Path("/gem5"))
    parser.add_argument("--trace", action="store_true")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd().parent,
        help="Host workspace directory mounted at /workspace.",
    )
    args = parser.parse_args()

    trials = json.loads(args.trials.read_text())
    args.outdir.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]

    failures = 0
    for trial in trials:
        name = str(trial["name"])
        trial_out = args.outdir / name
        trial_out.mkdir(parents=True, exist_ok=True)
        log_path = trial_out / "stdout.log"
        trace_raw = trial_out / "trace.raw.log"
        trace_jsonl = trial_out / "trace.jsonl"
        for stale in (log_path, trace_raw, trace_jsonl):
            if stale.exists():
                stale.unlink()
        try:
            trial_rel = trial_out.resolve().relative_to(root)
            m5out_path = f"/workspace/pace-new/{trial_rel.as_posix()}"
        except ValueError:
            m5out_path = (
                str(trial_out.resolve()) if
                (args.gem5_root / "build" / "Garnet_standalone" /
                 "gem5.debug").exists() else
                f"/workspace/pace-new/{trial_out.as_posix()}"
            )

        gem5_bin = "./build/Garnet_standalone/gem5.debug"
        gem5_cmd = [gem5_bin]
        if args.trace:
            gem5_cmd += [
                "--debug-flags=RubyNetwork,GarnetSyntheticTraffic",
                "--debug-file=trace.raw.log",
            ]
        gem5_cmd += [
            "-d", m5out_path,
            "configs/example/garnet_synth_traffic.py",
            *trial_args(trial),
        ]
        if (args.gem5_root / "build" / "Garnet_standalone" / "gem5.debug").exists():
            shell_cmd = "cd " + str(args.gem5_root) + " && " + " ".join(gem5_cmd)
            cmd = ["sh", "-lc", shell_cmd]
        else:
            shell_cmd = "cd /gem5 && " + " ".join(gem5_cmd)
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{args.gem5_volume}:/gem5:rw",
                "-v", f"{args.workspace.resolve()}:/workspace:rw",
                args.image,
                "sh", "-lc", shell_cmd,
            ]

        print(f"[gem5] {name}")
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        log_path.write_text(proc.stdout)
        if proc.returncode != 0:
            failures += 1
            print(f"  FAIL rc={proc.returncode} log={log_path}")
        else:
            if args.trace:
                extracted = subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).resolve().parent /
                            "extract_gem5_trace.py"),
                        str(trace_raw),
                        str(trace_jsonl),
                    ],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                if extracted.returncode != 0:
                    failures += 1
                    log_path.write_text(proc.stdout + "\n" + extracted.stdout)
                    print(f"  FAIL trace_extract log={log_path}")
                    continue
                print(f"  TRACE {trace_jsonl}")
            print(f"  PASS log={log_path}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
