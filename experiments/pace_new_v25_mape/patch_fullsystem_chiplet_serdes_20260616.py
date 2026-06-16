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
SCRIPT_DIR = Path(
    "/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/"
    "pace_new_v25_mape_20260606/scripts"
)
PACE_TOPO_BUILDER = SCRIPT_DIR / "build_pace_chiplet_topology.py"


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
            if width != flit_width:
                link.src_serdes = True
                link.src_net_bridge = NetworkBridge(
                    link=link.network_link,
                    vtype=\"OBJECT_LINK\",
                    width=flit_width,
                )
                link.src_cred_bridge = NetworkBridge(
                    link=link.credit_link,
                    vtype=\"LINK_OBJECT\",
                    width=flit_width,
                )
            if width != flit_width:
                link.dst_serdes = True
                link.dst_net_bridge = NetworkBridge(
                    link=link.network_link,
                    vtype=\"LINK_OBJECT\",
                    width=flit_width,
                )
                link.dst_cred_bridge = NetworkBridge(
                    link=link.credit_link,
                    vtype=\"OBJECT_LINK\",
                    width=flit_width,
                )
            int_links.append(link)
            link_count += 1
"""
    if old in text:
        PACE_CHIPLET.write_text(text.replace(old, new))
        print(f"patched {PACE_CHIPLET}")
    elif "if width != routers[src].width:" in text:
        text = text.replace("if width != routers[src].width:", "if width != flit_width:")
        text = text.replace("if width != routers[dst].width:", "if width != flit_width:")
        text = text.replace("width=routers[src].width,", "width=flit_width,")
        text = text.replace("width=routers[dst].width,", "width=flit_width,")
        PACE_CHIPLET.write_text(text)
        print(f"repatched {PACE_CHIPLET}")
    elif "if width != flit_width:" in text and "link.src_serdes = True" in text:
        print(f"already patched {PACE_CHIPLET}")
    else:
        raise RuntimeError("PACE_Chiplet.py add_link block not found")


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


def patch_pace_topology_builder() -> None:
    text = PACE_TOPO_BUILDER.read_text()
    old = """    def add_link(src: int, dst: int, src_out: str, dst_in: str,
                 latency: int, weight: int, width: int) -> None:
        nonlocal link_id
        int_links.append({
            "link_id": link_id,
            "src_node": src,
            "dst_node": dst,
            "src_outport": src_out,
            "dst_inport": dst_in,
            "latency": latency,
            "weight": weight,
            "width": width,
        })
        link_id += 1
"""
    new = """    def add_link(src: int, dst: int, src_out: str, dst_in: str,
                 latency: int, weight: int, width: int) -> None:
        nonlocal link_id
        int_links.append({
            "link_id": link_id,
            "src_node": src,
            "dst_node": dst,
            "src_outport": src_out,
            "dst_inport": dst_in,
            "latency": latency,
            "weight": weight,
            "width": width,
            "src_cdc": False,
            "dst_cdc": False,
            "src_serdes": width != routers[src]["width"],
            "dst_serdes": width != routers[dst]["width"],
        })
        link_id += 1
"""
    if old in text:
        PACE_TOPO_BUILDER.write_text(text.replace(old, new))
        print(f"patched {PACE_TOPO_BUILDER}")
    elif '"src_serdes": width != routers[src]["width"]' in text:
        print(f"already patched {PACE_TOPO_BUILDER}")
    else:
        raise RuntimeError("build_pace_chiplet_topology.py add_link block not found")


def main() -> None:
    patch_chiplet()
    patch_cmesh()
    patch_pace_topology_builder()


if __name__ == "__main__":
    main()
