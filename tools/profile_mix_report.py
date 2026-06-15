#!/usr/bin/env python3
"""Summarize PACE component traffic profile mix and burst statistics.

This is an experiment-analysis helper. It does not participate in simulation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ClassKey = tuple[int, int]


def _packet_count(value: Any) -> float:
    if isinstance(value, dict):
        return float(value.get("packets", 0.0))
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _load_profile(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    traffic_root = data.get("traffic", {})
    traffic = traffic_root.get("packet_flits_by_vnet", traffic_root)
    classes: dict[ClassKey, float] = {}
    total = 0.0

    for first_key, nested in traffic.items():
        if not isinstance(nested, dict):
            continue
        # Compact component profiles store packet_flits_by_vnet[vnet][flits].
        # Older profile experiments used traffic[src][vnet][flits].
        if all(not isinstance(value, dict) for value in nested.values()):
            vnet = int(first_key)
            for flits, value in nested.items():
                key = (vnet, int(flits))
                count = _packet_count(value)
                classes[key] = classes.get(key, 0.0) + count
                total += count
            continue
        for vnet, by_flits in nested.items():
            if not isinstance(by_flits, dict):
                continue
            for flits, value in by_flits.items():
                key = (int(vnet), int(flits))
                count = _packet_count(value)
                classes[key] = classes.get(key, 0.0) + count
                total += count

    burst = data.get("burst", {}).get("flow_interarrival_by_source_vnet_flits", {})
    cv_weighted_sum: dict[ClassKey, float] = {}
    cv_weight: dict[ClassKey, float] = {}
    max_cv: dict[ClassKey, float] = {}
    sources: dict[ClassKey, int] = {}

    for _src, by_vnet in burst.items():
        for vnet, by_flits in by_vnet.items():
            for flits, stats in by_flits.items():
                key = (int(vnet), int(flits))
                packets = float(stats.get("packets", 0.0))
                cv = float(stats.get("cv", 0.0))
                cv_weighted_sum[key] = cv_weighted_sum.get(key, 0.0) + cv * packets
                cv_weight[key] = cv_weight.get(key, 0.0) + packets
                max_cv[key] = max(max_cv.get(key, 0.0), cv)
                sources[key] = sources.get(key, 0) + 1

    avg_cv = {
        key: cv_weighted_sum[key] / cv_weight[key]
        for key in cv_weighted_sum
        if cv_weight[key] > 0.0
    }
    return {
        "path": path,
        "total": total,
        "classes": classes,
        "avg_cv": avg_cv,
        "max_cv": max_cv,
        "sources": sources,
    }


def _pct(count: float, total: float) -> float:
    return 100.0 * count / total if total else 0.0


def _class_sort_key(key: ClassKey) -> tuple[int, int]:
    return key[0], key[1]


def report(paths: list[Path], labels: list[str]) -> None:
    profiles = [_load_profile(path) for path in paths]
    baseline = profiles[0]

    print("profile,total_packets,vnet,flits,count,pct,delta_pct_vs_base,avg_cv,max_cv,sources")
    all_keys = sorted(
        {key for profile in profiles for key in profile["classes"]},
        key=_class_sort_key,
    )
    for label, profile in zip(labels, profiles):
        total = profile["total"]
        base_total = baseline["total"]
        for key in all_keys:
            count = profile["classes"].get(key, 0.0)
            pct = _pct(count, total)
            base_pct = _pct(baseline["classes"].get(key, 0.0), base_total)
            print(
                f"{label},{total:.0f},{key[0]},{key[1]},{count:.0f},"
                f"{pct:.6f},{pct - base_pct:.6f},"
                f"{profile['avg_cv'].get(key, 0.0):.6f},"
                f"{profile['max_cv'].get(key, 0.0):.6f},"
                f"{profile['sources'].get(key, 0)}"
            )

    print()
    print("summary_metric," + ",".join(labels))
    print(
        "total_packets,"
        + ",".join(f"{profile['total']:.0f}" for profile in profiles)
    )
    for key in all_keys:
        print(
            f"pct_v{key[0]}_f{key[1]},"
            + ",".join(
                f"{_pct(profile['classes'].get(key, 0.0), profile['total']):.6f}"
                for profile in profiles
            )
        )
    print(
        "pct_all_5flit,"
        + ",".join(
            f"{_pct(sum(c for (v, f), c in profile['classes'].items() if f == 5), profile['total']):.6f}"
            for profile in profiles
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profiles", nargs="+", type=Path)
    parser.add_argument("--labels", help="Comma-separated labels, one per profile.")
    args = parser.parse_args()

    labels = args.labels
    if labels is not None:
        labels = [label.strip() for label in labels.split(",")]
    if labels is None:
        labels = [path.parent.name for path in args.profiles]
    if len(labels) != len(args.profiles):
        raise SystemExit("--labels must have the same length as profiles")
    report(args.profiles, labels)


if __name__ == "__main__":
    main()
