#!/usr/bin/env python3
"""Cancel exact-phase jobs known to fail before useful simulation.

This is intentionally conservative: it only cancels experiment classes that
have already produced immediate gem5 configuration failures.
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

SCRATCH = Path("/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606")
MANIFESTS = [
    SCRATCH
    / "fullsys_flowstats_exactphase"
    / "exactphase_hugebatch_20260616a_manifest.csv",
    SCRATCH
    / "fullsys_flowstats_exactphase"
    / "exactphase_megabatch_20260616b_manifest.csv",
]


def is_known_bad(row: dict[str, str]) -> bool:
    # PACE_Chiplet_CMesh.py currently fails to import PACE_Chiplet.
    if row.get("topo_id") == "T5":
        return True

    # gem5 v25.1 Garnet rejects heterogeneous link/router widths without SerDes:
    # "Widths of link ... does not match that of Router..."
    if row.get("group") in {"chiplet_width", "chiplet_inter_width"}:
        return row.get("inter_width") != "128"

    return False


def main() -> None:
    job_ids: list[str] = []
    for manifest in MANIFESTS:
        if not manifest.exists():
            continue
        with manifest.open(newline="") as fh:
            for row in csv.DictReader(fh):
                if is_known_bad(row):
                    job_ids.append(row["job_id"])

    print(f"cancel_candidates={len(job_ids)}")
    if job_ids:
        subprocess.run(["scancel", *job_ids], check=False)


if __name__ == "__main__":
    main()
