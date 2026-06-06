from topologies.BaseTopology import SimpleTopology


class Mesh_XY(SimpleTopology):
    description = "Mesh_XY"

    def __init__(self, controllers):
        self.nodes = controllers

    def makeTopology(self, options, network, IntLink, ExtLink, Router):
        nodes = self.nodes

        num_routers = options.num_cpus
        num_rows = options.mesh_rows
        link_latency = options.link_latency
        router_latency = options.router_latency

        cntrls_per_router, remainder = divmod(len(nodes), num_routers)
        assert num_rows > 0 and num_rows <= num_routers
        num_columns = int(num_routers / num_rows)
        assert num_columns * num_rows == num_routers

        routers = [
            Router(
                router_id=i,
                latency=router_latency,
                width=options.ni_flit_size,
                x=i % num_columns,
                y=i // num_columns,
                z=0,
                chiplet="package",
            )
            for i in range(num_routers)
        ]
        network.routers = routers

        link_count = 0
        network_nodes = []
        remainder_nodes = []
        for node_index in range(len(nodes)):
            if node_index < (len(nodes) - remainder):
                network_nodes.append(nodes[node_index])
            else:
                remainder_nodes.append(nodes[node_index])

        ext_links = []
        for i, node in enumerate(network_nodes):
            cntrl_level, router_id = divmod(i, num_routers)
            assert cntrl_level < cntrls_per_router
            node.router_id = router_id
            ext_links.append(
                ExtLink(
                    link_id=link_count,
                    ext_node=node,
                    int_node=routers[router_id],
                    latency=link_latency,
                    width=_link_width(node, routers[router_id]),
                    ext_cdc=_clock_differs(node, routers[router_id]),
                    int_cdc=False,
                    ext_serdes=_width_differs(node, _link_width(node, routers[router_id])),
                    int_serdes=_width_differs(routers[router_id], _link_width(node, routers[router_id])),
                )
            )
            link_count += 1

        for i, node in enumerate(remainder_nodes):
            assert node.type == "DMA_Controller"
            assert i < remainder
            node.router_id = 0
            ext_links.append(
                ExtLink(
                    link_id=link_count,
                    ext_node=node,
                    int_node=routers[0],
                    latency=link_latency,
                    width=_link_width(node, routers[0]),
                    ext_cdc=_clock_differs(node, routers[0]),
                    int_cdc=False,
                    ext_serdes=_width_differs(node, _link_width(node, routers[0])),
                    int_serdes=_width_differs(routers[0], _link_width(node, routers[0])),
                )
            )
            link_count += 1

        network.ext_links = ext_links

        int_links = []

        for row in range(num_rows):
            for col in range(num_columns):
                if col + 1 < num_columns:
                    east_out = col + (row * num_columns)
                    west_in = (col + 1) + (row * num_columns)
                    int_links.append(
                        IntLink(
                            link_id=link_count,
                            src_node=routers[east_out],
                            dst_node=routers[west_in],
                            src_outport="East",
                            dst_inport="West",
                            latency=link_latency,
                            weight=1,
                        )
                    )
                    link_count += 1

        for row in range(num_rows):
            for col in range(num_columns):
                if col + 1 < num_columns:
                    east_in = col + (row * num_columns)
                    west_out = (col + 1) + (row * num_columns)
                    int_links.append(
                        IntLink(
                            link_id=link_count,
                            src_node=routers[west_out],
                            dst_node=routers[east_in],
                            src_outport="West",
                            dst_inport="East",
                            latency=link_latency,
                            weight=1,
                        )
                    )
                    link_count += 1

        for col in range(num_columns):
            for row in range(num_rows):
                if row + 1 < num_rows:
                    north_out = col + (row * num_columns)
                    south_in = col + ((row + 1) * num_columns)
                    int_links.append(
                        IntLink(
                            link_id=link_count,
                            src_node=routers[north_out],
                            dst_node=routers[south_in],
                            src_outport="North",
                            dst_inport="South",
                            latency=link_latency,
                            weight=2,
                        )
                    )
                    link_count += 1

        for col in range(num_columns):
            for row in range(num_rows):
                if row + 1 < num_rows:
                    north_in = col + (row * num_columns)
                    south_out = col + ((row + 1) * num_columns)
                    int_links.append(
                        IntLink(
                            link_id=link_count,
                            src_node=routers[south_out],
                            dst_node=routers[north_in],
                            src_outport="South",
                            dst_inport="North",
                            latency=link_latency,
                            weight=2,
                        )
                    )
                    link_count += 1

        network.int_links = int_links


def _clock_differs(controller, router):
    return bool(controller.clock_domain and router.clock_domain
                and controller.clock_domain != router.clock_domain)


def _link_width(a, b):
    if a.width and b.width:
        return min(a.width, b.width)
    return a.width or b.width


def _width_differs(obj, width):
    return bool(obj.width and width and obj.width != width)
