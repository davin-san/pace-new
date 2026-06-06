#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRIALS = ROOT / "verif" / "trials" / "garnet_deep_trace_matrix.json"
OUT = ROOT / "verif" / "out" / "gem5_trace"


def main() -> int:
    _run([
        sys.executable,
        str(ROOT / "tools" / "run_gem5_synth.py"),
        "--trace",
        "--trials",
        str(TRIALS),
        "--outdir",
        str(OUT),
    ])

    for trial in json.loads(TRIALS.read_text()):
        _validate_trace(OUT / str(trial["name"]) / "trace.jsonl")

    print("gem5_trace_generation: PASS")
    return 0


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
        raise AssertionError(f"{trace}: missing gem5 trace events: {sorted(missing)}")

    flitisize = [event for event in events if event["event"] == "ni.flitisize"]
    eject = [event for event in events if event["event"] == "ni.eject"]
    inject = [event for event in events if event["event"] == "traffic.inject"]
    deliver = [event for event in events if event["event"] == "traffic.deliver"]
    if not flitisize or not eject or not inject or not deliver:
        raise AssertionError(
            f"{trace}: expected injected/flitisized/ejected/delivered packets"
        )

    injected_packets = len(flitisize)
    if len(eject) != injected_packets:
        raise AssertionError(
            f"{trace}: flitisize/eject mismatch "
            f"{injected_packets} vs {len(eject)}"
        )
    for event in flitisize:
        if event["num_flits"] < 1:
            raise AssertionError(event)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )
    return proc


if __name__ == "__main__":
    raise SystemExit(main())
