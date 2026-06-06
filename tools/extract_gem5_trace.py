#!/usr/bin/env python3
"""Extract PACE_TRACE JSON payloads from a gem5 debug log."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TOKEN = "PACE_TRACE "


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("debug_log", type=Path)
    parser.add_argument("jsonl_out", type=Path)
    args = parser.parse_args()

    count = 0
    args.jsonl_out.parent.mkdir(parents=True, exist_ok=True)
    with args.debug_log.open() as src, args.jsonl_out.open("w") as dst:
        for line_number, line in enumerate(src, start=1):
            if TOKEN not in line:
                continue
            payload = line.split(TOKEN, 1)[1].strip()
            try:
                event = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"invalid PACE_TRACE JSON at {args.debug_log}:{line_number}: "
                    f"{payload}"
                ) from exc
            dst.write(json.dumps(event, sort_keys=True, separators=(",", ":")))
            dst.write("\n")
            count += 1

    print(f"extracted {count} events to {args.jsonl_out}")
    return 0 if count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
