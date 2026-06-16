#!/usr/bin/env python3
"""Patch experiment-only gem5 topology scripts for chiplet SerDes.

This does not modify Garnet C++ code. It updates the full-system experiment
topology scripts so heterogeneous inter-chiplet link widths use gem5's existing
NetworkBridge SerDes support.
"""

from __future__ import annotations

from pathlib import Path

GEM5_ROOT = Path(
    "/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606/"
    "gem5_profiler_build/gem5"
)
TOPO_DIR = GEM5_ROOT / "configs" / "topologies"
PACE_CHIPLET = TOPO_DIR / "PACE_Chiplet.py"
PACE_CMESH = TOPO_DIR / "PACE_Chiplet_CMesh.py"


def patch_chiplet() -> None:
    text = PACE_CHIPLET.read_text()

    old = """        def add_link(src, dst, src_out, dst_in, latency, weight, width):
            nonlocal link_count
            int_links.append(
                IntLink(
                    link_id=link_count,
                    src_node=routers[src],
                    dst_node=routers[dst],
                    src_outport=src_out,
                    dst_inport=dst_in,
                    latency=latency,
                    weight=weight,
                    width=width,
                )
            )
            link_count += 1
"""
    new = """        def add_link(src, dst, src_out, dst_in, latency, weight, width):
            nonlocal link_count
            link = IntLink(
                link_id=link_count,
                src_node=routers[src],
                dst_node=routers[dst],
                src_outport=src_out,
                dst_inport=dst_in,
                latency=latency,
                weight=weight,
                width=width,
            )
            if width != routers[src].width:
                link.src_serdes = True
                link.src_net_bridge = NetworkBridge(
                    link=link.network_link,
                    vtype=\"OBJECT_LINK\",
                    width=routers[src].width,
                )
                link.src_cred_bridge = NetworkBridge(
                    link=link.credit_link,
                    vtype=\"LINK_OBJECT\",
                    width=routers[src].width,
                )
            if width != routers[dst].width:
                link.dst_serdes = True
                link.dst_net_bridge = NetworkBridge(
                    link=link.network_link,
                    vtype=\"LINK_OBJECT\",
                    width=routers[dst].width,
                )
                link.dst_cred_bridge = NetworkBridge(
                    link=link.credit_link,
                    vtype=\"OBJECT_LINK\",
                    width=routers[dst].width,
                )
            int_links.append(link)
            link_count += 1
"""
    if old not in text:
        if "link.src_serdes = True" in text:
            print(f"already patched {PACE_CHIPLET}")
            return
        raise RuntimeError("PACE_Chiplet.py add_link block not found")

    PACE_CHIPLET.write_text(text.replace(old, new))
    print(f"patched {PACE_CHIPLET}")


def patch_cmesh() -> None:
    text = PACE_CMESH.read_text()
    old = "from PACE_Chiplet import PACE_Chiplet\n"
    new = "from topologies.PACE_Chiplet import PACE_Chiplet\n"
    if old in text:
        PACE_CMESH.write_text(text.replace(old, new))
        print(f"patched {PACE_CMESH}")
    elif new in text:
        print(f"already patched {PACE_CMESH}")
    else:
        raise RuntimeError("PACE_Chiplet_CMesh.py import form not recognized")


def main() -> None:
    patch_chiplet()
    patch_cmesh()


if __name__ == "__main__":
    main()
