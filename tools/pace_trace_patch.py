#!/usr/bin/env python3
"""Apply or restore reversible pace-new Garnet trace instrumentation.

This is for temporary trace worktrees only. Production `src/` must remain
byte-identical to gem5 Garnet.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.gem5_trace_patch import (  # noqa: E402
    BACKUP_SUFFIX,
    MARKER,
    _patch_crossbar,
    _patch_input_unit,
    _patch_network_interface,
    _patch_network_link,
    _patch_output_unit,
    _patch_router,
    _patch_routing_unit,
    _patch_switch_allocator,
)


PATCHERS = {
    "src/NetworkInterface.cc": _patch_network_interface,
    "src/Router.cc": _patch_router,
    "src/InputUnit.cc": _patch_input_unit,
    "src/SwitchAllocator.cc": _patch_switch_allocator,
    "src/CrossbarSwitch.cc": _patch_crossbar,
    "src/OutputUnit.cc": _patch_output_unit,
    "src/NetworkLink.cc": _patch_network_link,
    "src/RoutingUnit.cc": _patch_routing_unit,
}


def apply(root: Path) -> int:
    failures = 0
    for rel, patcher in PATCHERS.items():
        path = root / rel
        backup = path.with_name(path.name + BACKUP_SUFFIX)
        if not path.exists():
            print(f"{rel}: missing", file=sys.stderr)
            failures += 1
            continue

        text = path.read_text()
        if MARKER in text:
            print(f"{rel}: already patched")
            continue

        try:
            patched = patcher(text)
        except Exception as exc:
            print(f"{rel}: patch failed: {exc}", file=sys.stderr)
            failures += 1
            continue

        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(patched)
        print(f"{rel}: patched")
    return 1 if failures else 0


def restore(root: Path) -> int:
    failures = 0
    for rel in PATCHERS:
        path = root / rel
        backup = path.with_name(path.name + BACKUP_SUFFIX)
        if backup.exists():
            shutil.move(str(backup), str(path))
            print(f"{rel}: restored")
        elif path.exists():
            print(f"{rel}: no backup")
        else:
            print(f"{rel}: missing", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


def status(root: Path) -> int:
    for rel in PATCHERS:
        path = root / rel
        backup = path.with_name(path.name + BACKUP_SUFFIX)
        if not path.exists():
            state = "missing"
        elif MARKER in path.read_text():
            state = "patched"
        else:
            state = "clean"
        if backup.exists():
            state += ", backup"
        print(f"{rel}: {state}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("apply", "restore", "status"))
    parser.add_argument("root", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()

    root = args.root.resolve()
    if args.command == "apply":
        return apply(root)
    if args.command == "restore":
        return restore(root)
    return status(root)


if __name__ == "__main__":
    raise SystemExit(main())
