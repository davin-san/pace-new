#!/usr/bin/env python3
"""Add phase-conditioned endpoint counts to a component traffic profile.

The input profile already contains whole-ROI endpoint counts and per-phase
source/vnet marginals.  This tool constructs a maximum-entropy estimate of
per-phase endpoint counts that exactly matches the available phase marginals
after integer rounding.  If future profilers emit exact phase joint counts,
those should be preferred; this helper is for older profiles whose phase data
is marginal-only.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


ClassKey = tuple[int, int]


def _to_int_nested(raw: dict[str, Any]) -> dict[int, dict[int, dict[int, dict[int, int]]]]:
    out: dict[int, dict[int, dict[int, dict[int, int]]]] = {}
    for vnet, by_src in raw.items():
        out[int(vnet)] = {}
        for src, by_dst in by_src.items():
            out[int(vnet)][int(src)] = {}
            for dst, by_flits in by_dst.items():
                out[int(vnet)][int(src)][int(dst)] = {
                    int(flits): int(count)
                    for flits, count in by_flits.items()
                    if int(count) > 0
                }
    return out


def _source_targets(phase: dict[str, Any]) -> dict[int, int]:
    total = int(phase.get("total_packets", 0) or 0)
    fractions = {
        int(src): float(value)
        for src, value in (phase.get("source_fractions") or {}).items()
        if float(value) > 0.0
    }
    denom = sum(fractions.values())
    if total <= 0 or denom <= 0.0:
        return {}
    return _round_targets({
        src: total * (fraction / denom)
        for src, fraction in fractions.items()
    }, total)


def _class_targets(profile: dict[str, Any], phase: dict[str, Any]) -> dict[ClassKey, int]:
    whole = profile["traffic"]["packet_flits_by_vnet"]
    out: dict[ClassKey, int] = {}
    for vnet_text, packet_count in (phase.get("vnet_packets") or {}).items():
        vnet = int(vnet_text)
        packets = int(packet_count)
        if packets <= 0:
            continue
        flit_hist = {
            int(flits): int(count)
            for flits, count in whole.get(str(vnet), {}).items()
            if int(count) > 0
        }
        if not flit_hist:
            continue
        phase_flits = int((phase.get("vnet_flits") or {}).get(str(vnet), 0) or 0)
        sizes = sorted(flit_hist)
        if len(sizes) == 1 or phase_flits <= 0:
            scaled = {
                (vnet, flits): packets * (count / sum(flit_hist.values()))
                for flits, count in flit_hist.items()
            }
            out.update(_round_targets(scaled, packets))
            continue
        if len(sizes) == 2:
            small, large = sizes
            large_count = (phase_flits - small * packets) / (large - small)
            large_count = max(0.0, min(float(packets), large_count))
            rounded = _round_targets({
                (vnet, small): packets - large_count,
                (vnet, large): large_count,
            }, packets)
            out.update(rounded)
            continue
        scaled = {
            (vnet, flits): packets * (count / sum(flit_hist.values()))
            for flits, count in flit_hist.items()
        }
        out.update(_round_targets(scaled, packets))
    return out


def _round_targets(values: dict[Any, float], target_sum: int) -> dict[Any, int]:
    floors = {key: int(math.floor(max(0.0, value))) for key, value in values.items()}
    remainder = target_sum - sum(floors.values())
    order = sorted(
        values,
        key=lambda key: (max(0.0, values[key]) - floors[key], str(key)),
        reverse=True,
    )
    out = dict(floors)
    for key in order[:max(0, remainder)]:
        out[key] += 1
    return {key: value for key, value in out.items() if value > 0}


def _ipf(
    base: dict[tuple[int, ClassKey], float],
    row_targets: dict[int, int],
    col_targets: dict[ClassKey, int],
    iterations: int,
) -> dict[tuple[int, ClassKey], float]:
    weights = {
        key: value if value > 0.0 else 1.0e-9
        for key, value in base.items()
        if row_targets.get(key[0], 0) > 0 and col_targets.get(key[1], 0) > 0
    }
    for src in row_targets:
        for klass in col_targets:
            weights.setdefault((src, klass), 1.0e-9)
    for _ in range(iterations):
        row_sums: dict[int, float] = defaultdict(float)
        for (src, _), value in weights.items():
            row_sums[src] += value
        for key in list(weights):
            src, _ = key
            if row_sums[src] > 0.0:
                weights[key] *= row_targets[src] / row_sums[src]
        col_sums: dict[ClassKey, float] = defaultdict(float)
        for (_, klass), value in weights.items():
            col_sums[klass] += value
        for key in list(weights):
            _, klass = key
            if col_sums[klass] > 0.0:
                weights[key] *= col_targets[klass] / col_sums[klass]
    return weights


def _whole_source_class_counts(
    joint: dict[int, dict[int, dict[int, dict[int, int]]]]
) -> dict[tuple[int, ClassKey], float]:
    counts: dict[tuple[int, ClassKey], float] = defaultdict(float)
    for vnet, by_src in joint.items():
        for src, by_dst in by_src.items():
            for by_flits in by_dst.values():
                for flits, count in by_flits.items():
                    counts[(src, (vnet, flits))] += count
    return counts


def _distribute_destinations(
    joint: dict[int, dict[int, dict[int, dict[int, int]]]],
    source_class_counts: dict[tuple[int, ClassKey], int],
) -> dict[str, dict[str, dict[str, dict[str, int]]]]:
    out: dict[str, dict[str, dict[str, dict[str, int]]]] = {}
    for (src, (vnet, flits)), total in source_class_counts.items():
        dest_weights: dict[int, int] = {}
        for dst, by_flits in joint.get(vnet, {}).get(src, {}).items():
            count = by_flits.get(flits, 0)
            if count > 0:
                dest_weights[dst] = count
        if not dest_weights:
            continue
        rounded = _round_targets({
            dst: total * (count / sum(dest_weights.values()))
            for dst, count in dest_weights.items()
        }, total)
        for dst, count in rounded.items():
            out.setdefault(str(vnet), {}).setdefault(str(src), {}).setdefault(
                str(dst), {})[str(flits)] = count
    return out


def condition_profile(profile: dict[str, Any], iterations: int) -> dict[str, Any]:
    output = copy.deepcopy(profile)
    joint = _to_int_nested(
        profile["traffic"]["src_dst_ni_flits_counts_by_vnet"])
    base = _whole_source_class_counts(joint)
    for phase in output.get("phases", []):
        row_targets = _source_targets(phase)
        col_targets = _class_targets(profile, phase)
        if not row_targets or not col_targets:
            continue
        weights = _ipf(base, row_targets, col_targets, iterations)
        rounded = _round_targets(weights, sum(row_targets.values()))
        phase["src_dst_ni_flits_counts_by_vnet"] = _distribute_destinations(
            joint, rounded)
        phase["phase_conditioning"] = {
            "method": "source_vnet_flit_ipf_max_entropy",
            "iterations": iterations,
        }
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--iterations", type=int, default=40)
    args = parser.parse_args()

    profile = json.loads(args.input.read_text())
    conditioned = condition_profile(profile, args.iterations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(conditioned, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
