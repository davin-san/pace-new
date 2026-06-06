from topologies.BaseTopology import SimpleTopology


class HeteroChiplet(SimpleTopology):
    """Package topology for 2.5D and 3D heterogeneous chiplet designs.

    The topology is intentionally data driven. A chiplet spec describes router
    grids and explicit cross-chiplet links. The generated objects still follow
    gem5's Router/IntLink/ExtLink shape, including width, CDC, SerDes, link
    latency, link weight, and supported-vnet metadata.
    """

    description = "HeteroChiplet"

    def __init__(self, controllers):
        self.nodes = controllers

    def makeTopology(self, options, network, IntLink, ExtLink, Router):
        spec = options.chiplet_spec
        if not spec:
            raise ValueError("HeteroChiplet requires --chiplet-spec")

        link_latency = options.link_latency
        router_latency = options.router_latency
        routers = []
        router_by_key = {}
        link_count = 0

        for chiplet in spec["chiplets"]:
            chiplet_id = str(chiplet["id"])
            rows = int(chiplet.get("rows", 1))
            cols = int(chiplet.get("cols", 1))
            layers = int(chiplet.get("layers", 1))
            base_x = int(chiplet.get("x", 0))
            base_y = int(chiplet.get("y", 0))
            base_z = int(chiplet.get("z", 0))
            width = int(chiplet.get("width", options.ni_flit_size))
            latency = int(chiplet.get("router_latency", router_latency))
            clock_domain = chiplet.get("clock_domain")

            for z in range(layers):
                for y in range(rows):
                    for x in range(cols):
                        router = Router(
                            router_id=len(routers),
                            latency=latency,
                            width=width,
                            x=base_x + x,
                            y=base_y + y,
                            z=base_z + z,
                            chiplet=chiplet_id,
                            clock_domain=clock_domain,
                        )
                        routers.append(router)
                        router_by_key[(chiplet_id, x, y, z)] = router

        network.routers = routers

        int_links = []
        for chiplet in spec["chiplets"]:
            chiplet_id = str(chiplet["id"])
            rows = int(chiplet.get("rows", 1))
            cols = int(chiplet.get("cols", 1))
            layers = int(chiplet.get("layers", 1))
            mesh_latency = int(chiplet.get("link_latency", link_latency))

            for z in range(layers):
                for y in range(rows):
                    for x in range(cols - 1):
                        a = router_by_key[(chiplet_id, x, y, z)]
                        b = router_by_key[(chiplet_id, x + 1, y, z)]
                        link_count = _add_bidirectional(
                            int_links, IntLink, link_count, a, b,
                            "East", "West", "West", "East",
                            mesh_latency, 1,
                        )

            for z in range(layers):
                for x in range(cols):
                    for y in range(rows - 1):
                        a = router_by_key[(chiplet_id, x, y, z)]
                        b = router_by_key[(chiplet_id, x, y + 1, z)]
                        link_count = _add_bidirectional(
                            int_links, IntLink, link_count, a, b,
                            "North", "South", "South", "North",
                            mesh_latency, 2,
                        )

            for z in range(layers - 1):
                for y in range(rows):
                    for x in range(cols):
                        a = router_by_key[(chiplet_id, x, y, z)]
                        b = router_by_key[(chiplet_id, x, y, z + 1)]
                        link_count = _add_bidirectional(
                            int_links, IntLink, link_count, a, b,
                            "Up", "Down", "Down", "Up",
                            int(chiplet.get("vertical_latency", mesh_latency)),
                            int(chiplet.get("vertical_weight", 3)),
                        )

        for link in spec.get("links", []):
            src = _router_from_ref(router_by_key, link["src"])
            dst = _router_from_ref(router_by_key, link["dst"])
            reverse = bool(link.get("bidirectional", True))
            src_out = link.get("src_outport", "Interposer")
            dst_in = link.get("dst_inport", "Interposer")
            rev_out = link.get("dst_outport", dst_in)
            rev_in = link.get("src_inport", src_out)
            latency = int(link.get("latency", link_latency))
            weight = int(link.get("weight", 4))
            width = int(link.get("width", min(src.width, dst.width)))
            supported_vnets = list(link.get("supported_vnets", []))

            int_links.append(_int_link(
                IntLink, link_count, src, dst, src_out, dst_in, latency,
                weight, width, supported_vnets,
            ))
            link_count += 1
            if reverse:
                int_links.append(_int_link(
                    IntLink, link_count, dst, src, rev_out, rev_in, latency,
                    weight, width, supported_vnets,
                ))
                link_count += 1

        network.int_links = int_links

        ext_links = []
        placement = spec.get("controller_placement", {})
        for node in self.nodes:
            router = _select_router(node, routers, router_by_key, placement)
            node.router_id = router.router_id
            node.chiplet = router.chiplet
            node.layer = router.z
            ext_links.append(
                ExtLink(
                    link_id=link_count,
                    ext_node=node,
                    int_node=router,
                    latency=link_latency,
                    width=_link_width(node, router),
                    ext_cdc=_clock_differs(node, router),
                    int_cdc=False,
                    ext_serdes=_width_differs(node, _link_width(node, router)),
                    int_serdes=_width_differs(router, _link_width(node, router)),
                )
            )
            link_count += 1
        network.ext_links = ext_links


def _add_bidirectional(links, IntLink, link_count, a, b, a_out, b_in,
                       b_out, a_in, latency, weight):
    width = min(a.width, b.width)
    links.append(_int_link(IntLink, link_count, a, b, a_out, b_in,
                           latency, weight, width, []))
    link_count += 1
    links.append(_int_link(IntLink, link_count, b, a, b_out, a_in,
                           latency, weight, width, []))
    return link_count + 1


def _int_link(IntLink, link_id, src, dst, src_outport, dst_inport, latency,
              weight, width, supported_vnets):
    return IntLink(
        link_id=link_id,
        src_node=src,
        dst_node=dst,
        src_outport=src_outport,
        dst_inport=dst_inport,
        latency=latency,
        weight=weight,
        width=width,
        supported_vnets=supported_vnets,
        src_cdc=_clock_differs(src, dst),
        dst_cdc=_clock_differs(src, dst),
        src_serdes=_width_differs(src, width),
        dst_serdes=_width_differs(dst, width),
    )


def _router_from_ref(router_by_key, ref):
    if isinstance(ref, dict):
        key = (
            str(ref["chiplet"]),
            int(ref.get("x", 0)),
            int(ref.get("y", 0)),
            int(ref.get("z", 0)),
        )
    else:
        key = (str(ref[0]), int(ref[1]), int(ref[2]), int(ref[3]))
    return router_by_key[key]


def _select_router(node, routers, router_by_key, placement):
    node_key = f"{node.type}:{node.version}"
    if node_key in placement:
        return _router_from_ref(router_by_key, placement[node_key])
    if str(node.node_id) in placement:
        return _router_from_ref(router_by_key, placement[str(node.node_id)])
    return routers[node.node_id % len(routers)]


def _clock_differs(a, b):
    return bool(a.clock_domain and b.clock_domain
                and a.clock_domain != b.clock_domain)


def _link_width(a, b):
    if a.width and b.width:
        return min(a.width, b.width)
    return a.width or b.width


def _width_differs(obj, width):
    return bool(obj.width and width and obj.width != width)
