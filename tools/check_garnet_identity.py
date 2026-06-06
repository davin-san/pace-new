#!/usr/bin/env python3
"""Verify that pace-new/src is byte-identical to gem5 Garnet.

This is the first conformance gate. The production Garnet logic must live in
pace-new/src with no local edits. All standalone compatibility code belongs
outside that directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


TRACKED_SUFFIXES = {".cc", ".hh", ".py"}
TRACKED_NAMES = {"SConscript", "README.txt"}


def tracked(path: Path) -> bool:
    return path.suffix in TRACKED_SUFFIXES or path.name in TRACKED_NAMES


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gem5-garnet",
        type=Path,
        default=Path("../gem5-25.1/src/mem/ruby/network/garnet"),
        help="Path to gem5 src/mem/ruby/network/garnet.",
    )
    parser.add_argument(
        "--pace-garnet",
        type=Path,
        default=Path("src"),
        help="Path to pace-new Garnet source mirror.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of text.",
    )
    args = parser.parse_args()

    gem5 = args.gem5_garnet.resolve()
    pace = args.pace_garnet.resolve()

    if not gem5.is_dir():
        raise SystemExit(f"gem5 Garnet directory not found: {gem5}")
    if not pace.is_dir():
        raise SystemExit(f"pace Garnet directory not found: {pace}")

    gem5_files = {p.name: p for p in gem5.iterdir() if p.is_file() and tracked(p)}
    pace_files = {p.name: p for p in pace.iterdir() if p.is_file() and tracked(p)}

    rows = []
    ok = True

    for name in sorted(gem5_files):
        src = gem5_files[name]
        dst = pace_files.get(name)
        if dst is None:
            rows.append({"file": name, "present": False, "exact": False})
            ok = False
            continue
        exact = sha256(src) == sha256(dst)
        rows.append({"file": name, "present": True, "exact": exact})
        ok = ok and exact

    extras = sorted(set(pace_files) - set(gem5_files))
    if extras:
        ok = False

    result = {
        "ok": ok,
        "gem5_count": len(gem5_files),
        "pace_count": len(pace_files),
        "exact_count": sum(1 for row in rows if row["exact"]),
        "missing": [row["file"] for row in rows if not row["present"]],
        "mismatched": [row["file"] for row in rows if row["present"] and not row["exact"]],
        "extras": extras,
        "rows": rows,
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"gem5 tracked files: {result['gem5_count']}")
        print(f"pace tracked files: {result['pace_count']}")
        print(f"byte-identical: {result['exact_count']}/{result['gem5_count']}")
        if result["missing"]:
            print("missing: " + ", ".join(result["missing"]))
        if result["mismatched"]:
            print("mismatched: " + ", ".join(result["mismatched"]))
        if result["extras"]:
            print("extras: " + ", ".join(result["extras"]))
        print("PASS" if ok else "FAIL")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
