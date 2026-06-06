from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Controller:
    type: str
    version: int
    node_id: int
    chiplet: str | None = None
    layer: int = 0
    router_id: int | None = None
    width: int | None = None
    clock_domain: str | None = None

    def to_json(self) -> dict[str, Any]:
        return _drop_none(asdict(self))


@dataclass
class Router:
    router_id: int
    latency: int = 1
    width: int = 16
    x: int | None = None
    y: int | None = None
    z: int = 0
    chiplet: str | None = None
    clock_domain: str | None = None

    def to_json(self) -> dict[str, Any]:
        return _drop_none(asdict(self))


@dataclass
class NetworkLink:
    link_id: int
    link_latency: int = 1
    vcs_per_vnet: int = 4
    virt_nets: int = 3
    supported_vnets: list[int] = field(default_factory=list)
    width: int = 16

    def to_json(self) -> dict[str, Any]:
        return _drop_none(asdict(self))


@dataclass
class CreditLink(NetworkLink):
    pass


@dataclass
class NetworkBridge:
    link_id: int
    link: int
    vtype: str
    width: int
    serdes_latency: int = 1
    cdc_latency: int = 1

    def to_json(self) -> dict[str, Any]:
        return _drop_none(asdict(self))


@dataclass
class ExtLink:
    link_id: int
    ext_node: Controller
    int_node: Router
    latency: int = 1
    bandwidth_factor: int = 16
    weight: int = 1
    supported_vnets: list[int] = field(default_factory=list)
    width: int | None = None
    ext_cdc: bool = False
    int_cdc: bool = False
    ext_serdes: bool = False
    int_serdes: bool = False

    def to_json(self) -> dict[str, Any]:
        width = self.width if self.width is not None else self.int_node.width
        return _drop_none({
            "link_id": self.link_id,
            "ext_node": self.ext_node.node_id,
            "int_node": self.int_node.router_id,
            "latency": self.latency,
            "bandwidth_factor": self.bandwidth_factor,
            "weight": self.weight,
            "supported_vnets": self.supported_vnets,
            "width": width,
            "ext_cdc": self.ext_cdc,
            "int_cdc": self.int_cdc,
            "ext_serdes": self.ext_serdes,
            "int_serdes": self.int_serdes,
        })


@dataclass
class IntLink:
    link_id: int
    src_node: Router
    dst_node: Router
    src_outport: str = ""
    dst_inport: str = ""
    latency: int = 1
    bandwidth_factor: int = 16
    weight: int = 1
    supported_vnets: list[int] = field(default_factory=list)
    width: int | None = None
    src_cdc: bool = False
    dst_cdc: bool = False
    src_serdes: bool = False
    dst_serdes: bool = False

    def to_json(self) -> dict[str, Any]:
        width = self.width if self.width is not None else self.src_node.width
        return _drop_none({
            "link_id": self.link_id,
            "src_node": self.src_node.router_id,
            "dst_node": self.dst_node.router_id,
            "src_outport": self.src_outport,
            "dst_inport": self.dst_inport,
            "latency": self.latency,
            "bandwidth_factor": self.bandwidth_factor,
            "weight": self.weight,
            "supported_vnets": self.supported_vnets,
            "width": width,
            "src_cdc": self.src_cdc,
            "dst_cdc": self.dst_cdc,
            "src_serdes": self.src_serdes,
            "dst_serdes": self.dst_serdes,
        })


@dataclass
class Network:
    topology: str
    number_of_virtual_networks: int = 3
    vcs_per_vnet: int = 4
    ni_flit_size: int = 16
    routing_algorithm: int = 0
    garnet_deadlock_threshold: int = 50000
    routers: list[Router] = field(default_factory=list)
    ext_links: list[ExtLink] = field(default_factory=list)
    int_links: list[IntLink] = field(default_factory=list)

    def to_json(self, controllers: list[Controller]) -> dict[str, Any]:
        return {
            "schema": "pace.garnet.network.v1",
            "topology": self.topology,
            "number_of_virtual_networks": self.number_of_virtual_networks,
            "vcs_per_vnet": self.vcs_per_vnet,
            "ni_flit_size": self.ni_flit_size,
            "routing_algorithm": self.routing_algorithm,
            "garnet_deadlock_threshold": self.garnet_deadlock_threshold,
            "controllers": [c.to_json() for c in controllers],
            "routers": [r.to_json() for r in self.routers],
            "ext_links": [l.to_json() for l in self.ext_links],
            "int_links": [l.to_json() for l in self.int_links],
        }


def _drop_none(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if v is not None}
