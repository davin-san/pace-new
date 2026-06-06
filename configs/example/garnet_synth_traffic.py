#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
if str(CONFIGS) not in sys.path:
    sys.path.insert(0, str(CONFIGS))

from network import Controller, ExtLink, IntLink, Network, Router


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PACE Garnet standalone synthetic-traffic topology builder"
    )
    parser.add_argument("--num-cpus", type=int, required=True)
    parser.add_argument("--num-dirs", type=int, required=True)
    parser.add_argument("--network", choices=["garnet"], default="garnet")
    parser.add_argument("--topology", default="Mesh_XY")
    parser.add_argument("--mesh-rows", type=int, default=0)
    parser.add_argument("--sim-cycles", type=int, default=1000)
    parser.add_argument("--synthetic", default="uniform_random")
    parser.add_argument("--injectionrate", type=float, default=0.01)
    parser.add_argument("--inj-vnet", type=int, default=-1)
    parser.add_argument("--single-sender-id", type=int, default=-1)
    parser.add_argument("--single-dest-id", type=int, default=-1)
    parser.add_argument("--num-packets-max", type=int, default=-1)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--router-latency", type=int, default=1)
    parser.add_argument("--link-latency", type=int, default=1)
    parser.add_argument("--link-width-bits", type=int, default=128)
    parser.add_argument("--vcs-per-vnet", type=int, default=4)
    parser.add_argument("--num-vnets", type=int, default=3)
    parser.add_argument("--routing-algorithm", type=int, default=0)
    parser.add_argument("--garnet-deadlock-threshold", type=int, default=50000)
    parser.add_argument("--chiplet-spec", type=Path)
    parser.add_argument("--output", type=Path, default=Path("topology.json"))
    parser.add_argument(
        "--dump-json",
        action="store_true",
        help="Write the generated network JSON to stdout instead of --output",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.ni_flit_size = int(args.link_width_bits // 8)
    args.chiplet_spec = _load_chiplet_spec(args.chiplet_spec)

    controllers = _make_garnet_standalone_controllers(
        args.num_cpus,
        args.num_dirs,
        args.ni_flit_size,
    )
    network = Network(
        topology=args.topology,
        number_of_virtual_networks=args.num_vnets,
        vcs_per_vnet=args.vcs_per_vnet,
        ni_flit_size=args.ni_flit_size,
        routing_algorithm=args.routing_algorithm,
        garnet_deadlock_threshold=args.garnet_deadlock_threshold,
    )

    topology_class = getattr(
        importlib.import_module(f"topologies.{args.topology}"),
        args.topology,
    )
    topology = topology_class(controllers=controllers)
    topology.makeTopology(args, network, IntLink, ExtLink, Router)

    network_doc = network.to_json(controllers)
    network_doc["mesh_rows"] = args.mesh_rows

    doc = {
        "simulation": {
            "sim_cycles": args.sim_cycles,
            "synthetic": args.synthetic,
            "injectionrate": args.injectionrate,
            "inj_vnet": args.inj_vnet,
            "single_sender_id": args.single_sender_id,
            "single_dest_id": args.single_dest_id,
            "num_packets_max": args.num_packets_max,
            "seed": args.seed,
        },
        "network": network_doc,
    }

    text = json.dumps(doc, indent=2, sort_keys=True)
    if args.dump_json:
        print(text)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


def _make_garnet_standalone_controllers(num_cpus: int, num_dirs: int,
                                        width: int) -> list[Controller]:
    controllers: list[Controller] = []
    node_id = 0
    for version in range(num_cpus):
        controllers.append(Controller(
            type="L1Cache_Controller",
            version=version,
            node_id=node_id,
            width=width,
        ))
        node_id += 1
    for version in range(num_dirs):
        controllers.append(Controller(
            type="Directory_Controller",
            version=version,
            node_id=node_id,
            width=width,
        ))
        node_id += 1
    return controllers


def _load_chiplet_spec(path: Path | None):
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
