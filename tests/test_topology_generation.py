#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "configs" / "example" / "garnet_synth_traffic.py"


def main() -> int:
    mesh = _emit([
        "--num-cpus=4",
        "--num-dirs=4",
        "--network=garnet",
        "--topology=Mesh_XY",
        "--mesh-rows=2",
        "--sim-cycles=50",
        "--synthetic=uniform_random",
        "--injectionrate=0.01",
        "--seed=1",
    ])
    network = mesh["network"]
    assert network["schema"] == "pace.garnet.network.v1"
    assert len(network["controllers"]) == 8
    assert len(network["routers"]) == 4
    assert len(network["ext_links"]) == 8
    assert len(network["int_links"]) == 8
    assert [l["link_id"] for l in network["ext_links"]] == list(range(8))
    assert [l["link_id"] for l in network["int_links"]] == list(range(8, 16))
    assert network["int_links"][0]["src_outport"] == "East"
    assert network["int_links"][0]["dst_inport"] == "West"
    assert network["int_links"][4]["src_outport"] == "North"
    assert network["int_links"][4]["dst_inport"] == "South"

    hetero = _emit([
        "--num-cpus=4",
        "--num-dirs=4",
        "--network=garnet",
        "--topology=HeteroChiplet",
        "--chiplet-spec",
        str(ROOT / "configs" / "chiplets" / "example_3d.json"),
        "--sim-cycles=50",
        "--synthetic=uniform_random",
        "--injectionrate=0.01",
    ])
    hnet = hetero["network"]
    assert len(hnet["routers"]) == 12
    assert any(l["src_outport"] == "Up" for l in hnet["int_links"])
    assert any(l["src_cdc"] for l in hnet["int_links"])
    assert any(l["src_serdes"] for l in hnet["int_links"])
    assert any(l["ext_serdes"] for l in hnet["ext_links"])

    print("topology_generation: PASS")
    return 0


def _emit(args: list[str]) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--dump-json", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
