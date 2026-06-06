#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verif" / "out" / "pace_deep_trace"
WORK = OUT / "worktree"
TRIALS = ROOT / "verif" / "trials" / "garnet_deep_trace_matrix.json"


def main() -> int:
    _prepare_worktree()
    _run([sys.executable, "tools/pace_trace_patch.py", "apply", "."], cwd=WORK)
    build_env = os.environ.copy()
    build_env["CXXFLAGS"] = (
        "-std=c++17 -O0 -g -Wall -Wextra -Wno-unused-parameter "
        "-DPACE_ENABLE_DPRINTF_TRACE"
    )
    _run(["make", "clean", "all"], cwd=WORK, env=build_env)

    for trial in json.loads(TRIALS.read_text()):
        trial_out = OUT / str(trial["name"])
        trial_out.mkdir(parents=True, exist_ok=True)
        topology_json = trial_out / "topology.json"
        stats_json = trial_out / "stats.json"
        trace_jsonl = trial_out / "trace.jsonl"
        for stale in (topology_json, stats_json, trace_jsonl):
            if stale.exists():
                stale.unlink()
        _run([
            sys.executable,
            str(WORK / "configs" / "example" / "garnet_synth_traffic.py"),
            *generator_args(trial, topology_json),
        ], cwd=WORK)
        _run([
            str(WORK / "pace-new"),
            "--topology-json",
            str(topology_json),
            "--simulate",
            "--drain-cycles",
            "500",
            "--stats-json",
            str(stats_json),
            "--trace-jsonl",
            str(trace_jsonl),
        ], cwd=WORK)
        _validate_trace(trace_jsonl)

    print("pace_deep_trace_generation: PASS")
    return 0


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
    return args


def _validate_trace(trace: Path) -> None:
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    names = {event["event"] for event in events}
    required = {
        "traffic.inject",
        "message_buffer.enqueue",
        "message_buffer.dequeue",
        "ni.flitisize",
        "link.transfer",
        "router.wakeup",
        "input.flit",
        "routing.outport",
        "input.route_compute",
        "input.buffer_insert",
        "sa.wakeup",
        "sa.request",
        "vc.allocate",
        "sa.grant",
        "credit.decrement",
        "credit.send",
        "crossbar.traverse",
        "output.flit_enqueue",
        "credit.receive",
        "credit.increment",
        "ni.eject",
        "traffic.deliver",
    }
    missing = required - names
    if missing:
        raise AssertionError(f"{trace}: missing pace deep trace events: {sorted(missing)}")

    flitisize = [event for event in events if event["event"] == "ni.flitisize"]
    eject = [event for event in events if event["event"] == "ni.eject"]
    if not flitisize or len(eject) != len(flitisize):
        raise AssertionError(
            f"{trace}: flitisize/eject mismatch "
            f"{len(flitisize)} vs {len(eject)}"
        )


def _prepare_worktree() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    for dirname in ("src", "compat", "configs", "tools"):
        shutil.copytree(
            ROOT / dirname,
            WORK / dirname,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pace_trace.bak"),
        )
    (WORK / "verif" / "trials").mkdir(parents=True)
    shutil.copy2(
        TRIALS,
        WORK / "verif" / "trials" / "garnet_deep_trace_matrix.json",
    )
    shutil.copy2(ROOT / "Makefile", WORK / "Makefile")


def _run(
    cmd: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed in {cwd}: {' '.join(cmd)}\nOUTPUT:\n{proc.stdout}"
        )
    return proc


if __name__ == "__main__":
    raise SystemExit(main())
