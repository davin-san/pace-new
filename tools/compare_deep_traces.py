#!/usr/bin/env python3
"""Compare canonical deep Garnet trace events between gem5 and pace-new."""

from __future__ import annotations

import argparse
import filecmp
import json
from pathlib import Path
from typing import Any


FIELDS = {
    "ni.flitisize": (
        "ni", "src_router", "dest_ni", "dest_router", "vnet", "vc",
        "packet_id", "num_flits", "message_size",
    ),
    "link.transfer": (
        "vc", "vnet", "packet_id", "flit_id", "flit_type",
    ),
    "router.wakeup": ("router", "inports", "outports"),
    "input.flit": (
        "router", "inport", "vc", "vnet", "packet_id", "flit_id",
        "flit_type",
    ),
    "routing.outport": (
        "router", "vnet", "src_ni", "src_router", "dest_ni",
        "dest_router", "inport", "outport", "algorithm",
    ),
    "input.route_compute": (
        "router", "inport", "vc", "vnet", "packet_id", "dest_ni",
        "dest_router", "outport",
    ),
    "input.buffer_insert": (
        "router", "inport", "vc", "vnet", "packet_id", "flit_id",
    ),
    "sa.wakeup": ("router",),
    "sa.request": (
        "router", "inport", "invc", "outport", "outvc", "vnet",
    ),
    "vc.allocate": (
        "router", "outport", "inport", "invc", "outvc", "vnet",
    ),
    "sa.grant": (
        "router", "inport", "invc", "outport", "outvc", "vnet",
        "packet_id", "flit_id", "flit_type",
    ),
    "credit.decrement": ("router", "outport", "outvc", "credit_before"),
    "credit.send": ("router", "inport", "vc", "free"),
    "crossbar.traverse": (
        "router", "outport", "vc", "vnet", "packet_id", "flit_id",
        "flit_type",
    ),
    "output.flit_enqueue": (
        "router", "outport", "vc", "vnet", "packet_id", "flit_id",
        "flit_type",
    ),
    "credit.receive": ("router", "outport", "vc", "free"),
    "credit.increment": ("router", "outport", "outvc", "credit_before"),
    "ni.eject": ("ni", "vnet", "vc", "packet_id", "flit_id", "flit_type"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gem5_trace", type=Path)
    parser.add_argument("pace_trace", type=Path)
    parser.add_argument(
        "--canonical-dir",
        type=Path,
        help=(
            "Write deterministic canonical gem5.jsonl and pace.jsonl files "
            "and compare those files byte-for-byte."
        ),
    )
    args = parser.parse_args()

    gem5 = canonical_groups(args.gem5_trace)
    pace = canonical_groups(args.pace_trace)

    if args.canonical_dir:
        args.canonical_dir.mkdir(parents=True, exist_ok=True)
        gem5_canonical = args.canonical_dir / "gem5.canonical.jsonl"
        pace_canonical = args.canonical_dir / "pace.canonical.jsonl"
        write_canonical_jsonl(gem5, gem5_canonical)
        write_canonical_jsonl(pace, pace_canonical)
        if not filecmp.cmp(gem5_canonical, pace_canonical, shallow=False):
            mismatch = first_byte_mismatch(gem5_canonical, pace_canonical)
            raise AssertionError(
                "canonical trace byte mismatch: "
                f"gem5={gem5_canonical} pace={pace_canonical} "
                f"first_mismatch_byte={mismatch}"
            )
    else:
        compare_groups(gem5, pace)

    events = sum(len(group) for group in gem5)
    print(f"deep_trace_compare: PASS cycles={len(gem5)} events={events}")
    return 0


def compare_groups(gem5: list[list[dict[str, Any]]],
                   pace: list[list[dict[str, Any]]]) -> None:
    if len(gem5) != len(pace):
        raise AssertionError(
            f"canonical cycle count mismatch: gem5={len(gem5)} pace={len(pace)}"
        )
    for index, (left, right) in enumerate(zip(gem5, pace)):
        if left != right:
            raise AssertionError(
                f"trace mismatch at canonical cycle {index}:\n"
                f"gem5={left}\npace={right}"
            )


def write_canonical_jsonl(groups: list[list[dict[str, Any]]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as out:
        for cycle, group in enumerate(groups):
            for event in group:
                row = {"cycle": cycle, **event}
                out.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
                out.write("\n")


def first_byte_mismatch(left: Path, right: Path) -> int | str:
    with left.open("rb") as lhs, right.open("rb") as rhs:
        offset = 0
        while True:
            l_chunk = lhs.read(8192)
            r_chunk = rhs.read(8192)
            if l_chunk == r_chunk:
                if not l_chunk:
                    return "none"
                offset += len(l_chunk)
                continue
            for index, (l_byte, r_byte) in enumerate(zip(l_chunk, r_chunk)):
                if l_byte != r_byte:
                    return offset + index
            return offset + min(len(l_chunk), len(r_chunk))


def canonical_groups(path: Path) -> list[list[dict[str, Any]]]:
    packet_map = packet_id_map(path)
    by_tick: dict[int, list[dict[str, Any]]] = {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        name = event["event"]
        if name not in FIELDS:
            continue
        normalized = {"event": name}
        for field in FIELDS[name]:
            if field not in event:
                raise AssertionError(f"{path}: {name} missing {field}: {event}")
            normalized[field] = event[field]
        if "packet_id" in normalized and normalized.get("flit_type") != 4:
            normalized["packet_id"] = packet_map.get(
                int(normalized["packet_id"]), normalized["packet_id"]
            )
        by_tick.setdefault(int(event["tick"]), []).append(normalized)
    return [
        sorted(group, key=_stable_event_key)
        for _, group in sorted(by_tick.items())
    ]


def _stable_event_key(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


def packet_id_map(path: Path) -> dict[int, int]:
    occurrences: dict[tuple[int, int, int], int] = {}
    identities: list[tuple[tuple[int, int, int, int], int]] = []
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if event["event"] != "ni.flitisize":
            continue
        base = (int(event["ni"]), int(event["dest_ni"]), int(event["vnet"]))
        occurrence = occurrences.get(base, 0)
        occurrences[base] = occurrence + 1
        identities.append(((*base, occurrence), int(event["packet_id"])))
    return {
        packet_id: canonical
        for canonical, (_, packet_id) in enumerate(sorted(identities))
    }


if __name__ == "__main__":
    raise SystemExit(main())
