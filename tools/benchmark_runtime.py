#!/usr/bin/env python3
"""Benchmark pace-new and pace-lite runtime/RSS in a repeatable way."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
PACE_LITE = WORKSPACE / "pace-lite"
REPLAY_BENCHMARK_SCENARIOS = [
    "deterministic-mesh2x2",
    "mesh4x4-long-paths",
    "mesh4x4-contention",
    "mesh4x4-multiflit-vnet0",
    "mesh8x8-smoke",
]


def run(cmd: list[str], cwd: Path, *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=False,
    )


def measure(cmd: list[str], cwd: Path, repeats: int) -> dict[str, object]:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        maxrss_kb = 0
        stdout_chunks = []
        assert proc.stdout is not None
        while proc.poll() is None:
            maxrss_kb = max(maxrss_kb, read_proc_rss_kb(proc.pid))
            time.sleep(0.001)
        stdout_chunks.append(proc.stdout.read())
        maxrss_kb = max(maxrss_kb, read_proc_rss_kb(proc.pid))
        elapsed = time.perf_counter() - start
        samples.append({
            "returncode": proc.returncode or 0,
            "wall_seconds": elapsed,
            "maxrss_kb": maxrss_kb,
            "stdout": "".join(stdout_chunks),
        })
        if proc.returncode:
            break
    ok_samples = [s for s in samples if s["returncode"] == 0]
    if not ok_samples:
        return {"ok": False, "samples": samples}
    return {
        "ok": True,
        "samples": samples,
        "best_wall_seconds": min(s["wall_seconds"] for s in ok_samples),
        "avg_wall_seconds": sum(s["wall_seconds"] for s in ok_samples) / len(ok_samples),
        "maxrss_kb": max(s["maxrss_kb"] for s in ok_samples),
    }


def read_proc_rss_kb(pid: int) -> int:
    status = Path("/proc") / str(pid) / "status"
    try:
        for line in status.read_text().splitlines():
            if line.startswith("VmHWM:") or line.startswith("VmRSS:"):
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1])
    except OSError:
        return 0
    return 0


def build_pace_new(build: str) -> None:
    make = ["make", "clean", "all"]
    if build:
        make.append(f"BUILD={build}")
    proc = run(make, ROOT)
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout)


def build_pace_lite() -> None:
    proc = run(["make", "clean", "all"], PACE_LITE)
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout)


def bench_pace_new(repeats: int, build: str) -> dict[str, object]:
    build_pace_new(build)
    outdir = ROOT / "verif" / "out" / "bench"
    outdir.mkdir(parents=True, exist_ok=True)
    topology = outdir / f"pace_new_{build or 'default'}_mesh4x4.json"
    stats = outdir / f"pace_new_{build or 'default'}_mesh4x4_stats.json"
    generator = ROOT / "configs" / "example" / "garnet_synth_traffic.py"
    gen = run([
        sys.executable, str(generator),
        "--num-cpus", "16",
        "--num-dirs", "16",
        "--network", "garnet",
        "--topology", "Mesh_XY",
        "--mesh-rows", "4",
        "--sim-cycles", "20000",
        "--synthetic", "uniform_random",
        "--injectionrate", "0.01",
        "--num-packets-max", "64",
        "--inj-vnet", "2",
        "--seed", "11",
        "--output", str(topology),
    ], ROOT)
    if gen.returncode != 0:
        raise RuntimeError(gen.stdout)
    result = measure([
        str(ROOT / "pace-new"),
        "--topology-json", str(topology),
        "--simulate",
        "--drain-cycles", "500",
        "--stats-json", str(stats),
    ], ROOT, repeats)
    result["stats_json"] = str(stats)
    if stats.exists():
        result["stats"] = json.loads(stats.read_text())
    return result


def bench_pace_new_matched_2x2(repeats: int, build: str) -> dict[str, object]:
    build_pace_new(build)
    outdir = ROOT / "verif" / "out" / "bench"
    outdir.mkdir(parents=True, exist_ok=True)
    topology = outdir / f"pace_new_{build or 'default'}_matched_2x2.json"
    stats = outdir / f"pace_new_{build or 'default'}_matched_2x2_stats.json"
    generator = ROOT / "configs" / "example" / "garnet_synth_traffic.py"
    gen = run([
        sys.executable, str(generator),
        "--num-cpus", "2",
        "--num-dirs", "2",
        "--network", "garnet",
        "--topology", "Mesh_XY",
        "--mesh-rows", "2",
        "--sim-cycles", "10500",
        "--synthetic", "uniform_random",
        "--injectionrate", "0.01",
        "--num-packets-max", "64",
        "--inj-vnet", "0",
        "--seed", "11",
        "--output", str(topology),
    ], ROOT)
    if gen.returncode != 0:
        raise RuntimeError(gen.stdout)
    result = measure([
        str(ROOT / "pace-new"),
        "--topology-json", str(topology),
        "--simulate",
        "--drain-cycles", "500",
        "--stats-json", str(stats),
    ], ROOT, repeats)
    result["stats_json"] = str(stats)
    result["note"] = (
        "Matched 2x2 topology/envelope. pace-new uses gem5-style one-way "
        "synthetic traffic; pace-lite uses its response-generating traffic."
    )
    if stats.exists():
        result["stats"] = json.loads(stats.read_text())
    return result


def ensure_replay(outdir: Path, scenario: str = "deterministic-mesh2x2") -> Path:
    replay = outdir / f"{scenario}.replay.json"
    gen = run([
        sys.executable,
        str(ROOT / "tools" / "generate_replay.py"),
        "--scenario", scenario,
        "--output", str(replay),
    ], ROOT)
    if gen.returncode != 0:
        raise RuntimeError(gen.stdout)
    return replay


def generate_pace_new_replay_topology(replay: dict[str, object],
                                      topology: Path) -> None:
    generator = ROOT / "configs" / "example" / "garnet_synth_traffic.py"
    gen = run([
        sys.executable, str(generator),
        "--num-cpus", str(int(replay["nodes"])),
        "--num-dirs", "0",
        "--network", "garnet",
        "--topology", "Mesh_XY",
        "--mesh-rows", str(int(replay["mesh_rows"])),
        "--sim-cycles", str(int(replay["sim_cycles"])),
        "--synthetic", "uniform_random",
        "--injectionrate", "0.0",
        "--num-packets-max", "0",
        "--output", str(topology),
    ], ROOT)
    if gen.returncode != 0:
        raise RuntimeError(gen.stdout)


def generate_pace_lite_mesh_topology(replay: dict[str, object],
                                     topology: Path) -> None:
    rows = int(replay["mesh_rows"])
    gen = run([
        sys.executable,
        str(PACE_LITE / "python" / "conf_generator.py"),
        "--topology", str(WORKSPACE / "topologies" / "Mesh_XY.py"),
        "--rows", str(rows),
        "--cols", str(rows),
        "--num-cpus", str(int(replay["nodes"])),
        "--output", str(topology),
    ], PACE_LITE)
    if gen.returncode != 0:
        raise RuntimeError(gen.stdout)


def bench_pace_new_replay_scenario(
    scenario: str, repeats: int, build: str, *, already_built: bool = False
) -> dict[str, object]:
    if not already_built:
        build_pace_new(build)
    outdir = ROOT / "verif" / "out" / "bench" / "replay_matrix"
    outdir.mkdir(parents=True, exist_ok=True)
    replay_path = ensure_replay(outdir, scenario)
    replay = json.loads(replay_path.read_text())
    topology = outdir / f"pace_new_{build or 'default'}_{scenario}.json"
    stats = outdir / f"pace_new_{build or 'default'}_{scenario}_stats.json"
    generate_pace_new_replay_topology(replay, topology)
    result = measure([
        str(ROOT / "pace-new"),
        "--topology-json", str(topology),
        "--simulate",
        "--replay-json", str(replay_path),
        "--stats-json", str(stats),
    ], ROOT, repeats)
    result["scenario"] = scenario
    result["replay_json"] = str(replay_path)
    result["stats_json"] = str(stats)
    if stats.exists():
        result["stats"] = json.loads(stats.read_text())
    return result


def bench_pace_lite_replay_scenario(
    scenario: str, repeats: int, *, already_built: bool = False
) -> dict[str, object]:
    if not already_built:
        build_pace_lite()
    outdir = ROOT / "verif" / "out" / "bench" / "replay_matrix"
    outdir.mkdir(parents=True, exist_ok=True)
    replay_path = ensure_replay(outdir, scenario)
    replay = json.loads(replay_path.read_text())
    topology = outdir / f"pace_lite_{scenario}.conf"
    output = outdir / f"pace_lite_{scenario}_results.json"
    generate_pace_lite_mesh_topology(replay, topology)
    result = measure([
        str(PACE_LITE / "pace-lite"),
        "--profile", str(PACE_LITE / "test_profile.json"),
        "--topology", str(topology),
        "--output", str(output),
        "--replay", str(replay_path),
    ], PACE_LITE, repeats)
    result["scenario"] = scenario
    result["replay_json"] = str(replay_path)
    result["stats_json"] = str(output)
    if output.exists():
        result["stats"] = json.loads(output.read_text())
    return result


def bench_pace_new_replay_2x2(repeats: int, build: str) -> dict[str, object]:
    build_pace_new(build)
    outdir = ROOT / "verif" / "out" / "bench"
    outdir.mkdir(parents=True, exist_ok=True)
    replay = ensure_replay(outdir)
    topology = outdir / f"pace_new_{build or 'default'}_replay_2x2.json"
    stats = outdir / f"pace_new_{build or 'default'}_replay_2x2_stats.json"
    generator = ROOT / "configs" / "example" / "garnet_synth_traffic.py"
    gen = run([
        sys.executable, str(generator),
        "--num-cpus", "4",
        "--num-dirs", "0",
        "--network", "garnet",
        "--topology", "Mesh_XY",
        "--mesh-rows", "2",
        "--sim-cycles", "120",
        "--synthetic", "uniform_random",
        "--injectionrate", "0.0",
        "--num-packets-max", "0",
        "--output", str(topology),
    ], ROOT)
    if gen.returncode != 0:
        raise RuntimeError(gen.stdout)
    result = measure([
        str(ROOT / "pace-new"),
        "--topology-json", str(topology),
        "--simulate",
        "--replay-json", str(replay),
        "--stats-json", str(stats),
    ], ROOT, repeats)
    result["replay_json"] = str(replay)
    result["stats_json"] = str(stats)
    if stats.exists():
        result["stats"] = json.loads(stats.read_text())
    return result


def bench_pace_lite(repeats: int) -> dict[str, object]:
    build_pace_lite()
    outdir = ROOT / "verif" / "out" / "bench"
    outdir.mkdir(parents=True, exist_ok=True)
    output = outdir / "pace_lite_mesh2x2_results.json"
    result = measure([
        str(PACE_LITE / "pace-lite"),
        "--profile", str(PACE_LITE / "test_profile.json"),
        "--topology", str(PACE_LITE / "mesh2x2.conf"),
        "--output", str(output),
        "--uniform", "0.01",
        "--packets-per-node", "64",
        "--drain-cycles", "500",
        "--seed", "11",
    ], PACE_LITE, repeats)
    result["stats_json"] = str(output)
    if output.exists():
        result["stats"] = json.loads(output.read_text())
    return result


def bench_pace_lite_replay_2x2(repeats: int) -> dict[str, object]:
    build_pace_lite()
    outdir = ROOT / "verif" / "out" / "bench"
    outdir.mkdir(parents=True, exist_ok=True)
    replay = ensure_replay(outdir)
    output = outdir / "pace_lite_replay_2x2_results.json"
    result = measure([
        str(PACE_LITE / "pace-lite"),
        "--profile", str(PACE_LITE / "test_profile.json"),
        "--topology", str(PACE_LITE / "mesh2x2.conf"),
        "--output", str(output),
        "--replay", str(replay),
    ], PACE_LITE, repeats)
    result["replay_json"] = str(replay)
    result["stats_json"] = str(output)
    if output.exists():
        result["stats"] = json.loads(output.read_text())
    return result


def write_matched_pace_lite_profile(path: Path) -> None:
    path.write_text(json.dumps({
        "benchmark": "matched_2x2",
        "num_cpus": 2,
        "num_dirs": 2,
        "lambda": 0.01,
        "per_source_rate": {
            "0": 0.01,
            "1": 0.01,
            "2": 0.0,
            "3": 0.0,
        },
        "dir_fractions": {
            "0": 0.5,
            "1": 0.5,
        },
        "directory_remapping": {
            "0": 2,
            "1": 3,
        },
        "vnet_fractions": {
            "0": 1.0,
            "1": 0.0,
            "2": 0.0,
        },
        "response_data_prob": 0.0,
        "mshr_slots": 0,
        "data_packet_flits": 1,
        "ctrl_packet_flits": 1,
    }, indent=2) + "\n")


def bench_pace_lite_matched_2x2(repeats: int) -> dict[str, object]:
    build_pace_lite()
    outdir = ROOT / "verif" / "out" / "bench"
    outdir.mkdir(parents=True, exist_ok=True)
    profile = outdir / "pace_lite_matched_2x2_profile.json"
    output = outdir / "pace_lite_matched_2x2_results.json"
    write_matched_pace_lite_profile(profile)
    result = measure([
        str(PACE_LITE / "pace-lite"),
        "--profile", str(profile),
        "--topology", str(PACE_LITE / "mesh2x2.conf"),
        "--output", str(output),
        "--packets-per-node", "64",
        "--drain-cycles", "500",
        "--seed", "11",
        "--mshr-limit", "0",
    ], PACE_LITE, repeats)
    result["stats_json"] = str(output)
    result["profile_json"] = str(profile)
    result["note"] = (
        "Matched 2x2 topology/envelope. pace-lite emits directory responses; "
        "pace-new's current synthetic benchmark does not."
    )
    if output.exists():
        result["stats"] = json.loads(output.read_text())
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--pace-new-build", default="")
    parser.add_argument("--skip-pace-lite", action="store_true")
    parser.add_argument(
        "--suite",
        choices=["default", "matched-2x2", "replay-2x2", "replay-matrix"],
        default="default",
    )
    args = parser.parse_args()

    if args.suite == "replay-matrix":
        build_pace_new(args.pace_new_build)
        report = {
            "suite": "replay-matrix",
            "scenarios": REPLAY_BENCHMARK_SCENARIOS,
            "pace_new": {
                scenario: bench_pace_new_replay_scenario(
                    scenario,
                    args.repeats,
                    args.pace_new_build,
                    already_built=True,
                )
                for scenario in REPLAY_BENCHMARK_SCENARIOS
            },
        }
        if not args.skip_pace_lite:
            build_pace_lite()
            report["pace_lite"] = {
                scenario: bench_pace_lite_replay_scenario(
                    scenario,
                    args.repeats,
                    already_built=True,
                )
                for scenario in REPLAY_BENCHMARK_SCENARIOS
            }
    elif args.suite == "replay-2x2":
        report = {
            "suite": "replay-2x2",
            "pace_new": bench_pace_new_replay_2x2(
                args.repeats, args.pace_new_build),
        }
        if not args.skip_pace_lite:
            report["pace_lite"] = bench_pace_lite_replay_2x2(args.repeats)
    elif args.suite == "matched-2x2":
        report = {
            "suite": "matched-2x2",
            "pace_new": bench_pace_new_matched_2x2(
                args.repeats, args.pace_new_build),
        }
        if not args.skip_pace_lite:
            report["pace_lite"] = bench_pace_lite_matched_2x2(args.repeats)
    else:
        report = {
            "suite": "default",
            "pace_new": bench_pace_new(args.repeats, args.pace_new_build),
        }
        if not args.skip_pace_lite:
            report["pace_lite"] = bench_pace_lite(args.repeats)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
