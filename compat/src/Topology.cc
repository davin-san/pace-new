#include "mem/ruby/network/Topology.hh"

#include <algorithm>
#include <cassert>

#include "mem/ruby/network/BasicLink.hh"
#include "mem/ruby/network/Network.hh"
#include "pace_compat/Trace.hh"

namespace gem5
{
namespace ruby
{

namespace
{
constexpr int infinite_latency = 10000;
}

Topology::Topology(uint32_t num_nodes, uint32_t num_routers,
                   uint32_t num_vnets)
    : m_nodes(num_nodes), m_number_of_switches(num_routers),
      m_vnets(num_vnets)
{
    assert(m_nodes > 1);
}

void
Topology::addExtLink(NodeID node, SwitchID router, BasicLink* link)
{
    const SwitchID ext_idx1 = node;
    const SwitchID ext_idx2 = node + m_nodes;
    const SwitchID int_idx = router + 2 * m_nodes;
    pace::traceEvent("topology.ext_link", {
        {"node", pace::traceValue(node)},
        {"router", pace::traceValue(router)},
        {"ext_in_switch", pace::traceValue(ext_idx1)},
        {"ext_out_switch", pace::traceValue(ext_idx2)},
        {"int_switch", pace::traceValue(int_idx)},
        {"latency", pace::traceValue(link ? link->m_latency : 0)},
        {"weight", pace::traceValue(link ? link->m_weight : 0)},
    });
    addLink(ext_idx1, int_idx, link);
    addLink(int_idx, ext_idx2, link);
}

void
Topology::addIntLink(SwitchID src, SwitchID dest, BasicLink* link,
                     PortDirection src_outport_dirn,
                     PortDirection dst_inport_dirn)
{
    pace::traceEvent("topology.int_link", {
        {"src_router", pace::traceValue(src)},
        {"dst_router", pace::traceValue(dest)},
        {"src_outport", pace::traceValue(src_outport_dirn)},
        {"dst_inport", pace::traceValue(dst_inport_dirn)},
        {"latency", pace::traceValue(link ? link->m_latency : 0)},
        {"weight", pace::traceValue(link ? link->m_weight : 0)},
    });
    addLink(src + 2 * m_nodes, dest + 2 * m_nodes, link,
            src_outport_dirn, dst_inport_dirn);
}

void
Topology::createLinks(Network* net)
{
    SwitchID max_switch_id = 0;
    for (const auto& item : m_link_map) {
        max_switch_id = std::max(max_switch_id, item.first.first);
        max_switch_id = std::max(max_switch_id, item.first.second);
    }

    const int num_switches = max_switch_id + 1;
    Matrix topology_weights(
        m_vnets, std::vector<std::vector<int>>(
            num_switches, std::vector<int>(num_switches, infinite_latency)));
    Matrix component_latencies(
        num_switches, std::vector<std::vector<int>>(
            num_switches, std::vector<int>(m_vnets, -1)));
    Matrix component_inter_switches(
        num_switches, std::vector<std::vector<int>>(
            num_switches, std::vector<int>(m_vnets, 0)));

    for (int i = 0; i < static_cast<int>(topology_weights[0].size()); i++) {
        for (uint32_t v = 0; v < m_vnets; v++) {
            topology_weights[v][i][i] = 0;
        }
    }

    for (const auto& link_group : m_link_map) {
        const int src = link_group.first.first;
        const int dst = link_group.first.second;
        std::vector<bool> vnet_done(m_vnets, false);

        for (const auto& link_entry : link_group.second) {
            BasicLink* link = link_entry.link;
            if (link->mVnets.empty()) {
                for (uint32_t v = 0; v < m_vnets; v++) {
                    fatal_if(vnet_done[v], "Two links for same vnet");
                    component_latencies[src][dst][v] = link->m_latency;
                    topology_weights[v][src][dst] = link->m_weight;
                    vnet_done[v] = true;
                }
            } else {
                for (int vnet : link->mVnets) {
                    fatal_if(vnet >= static_cast<int>(m_vnets),
                             "Not enough virtual networks");
                    fatal_if(vnet_done[vnet], "Two links for same vnet");
                    component_latencies[src][dst][vnet] = link->m_latency;
                    topology_weights[vnet][src][dst] = link->m_weight;
                    vnet_done[vnet] = true;
                }
            }
        }
    }

    Matrix dist = shortest_path(topology_weights, component_latencies,
                                component_inter_switches);

    for (int i = 0; i < static_cast<int>(topology_weights[0].size()); i++) {
        for (int j = 0; j < static_cast<int>(topology_weights[0][i].size());
             j++) {
            std::vector<NetDest> routing_map(m_vnets);
            bool real_link = false;

            for (uint32_t v = 0; v < m_vnets; v++) {
                int weight = topology_weights[v][i][j];
                if (weight > 0 && weight != infinite_latency) {
                    real_link = true;
                    routing_map[v] =
                        shortest_path_to_node(i, j, topology_weights, dist, v);
                }
            }

            if (real_link) {
                pace::traceEvent("topology.make_link", {
                    {"src_switch", pace::traceValue(i)},
                    {"dst_switch", pace::traceValue(j)},
                });
                makeLink(net, i, j, routing_map);
            }
        }
    }
}

void
Topology::addLink(SwitchID src, SwitchID dest, BasicLink* link,
                  PortDirection src_outport_dirn,
                  PortDirection dst_inport_dirn)
{
    assert(src <= m_number_of_switches + m_nodes + m_nodes);
    assert(dest <= m_number_of_switches + m_nodes + m_nodes);

    LinkEntry entry;
    entry.link = link;
    entry.src_outport_dirn = src_outport_dirn;
    entry.dst_inport_dirn = dst_inport_dirn;
    m_link_map[{src, dest}].push_back(entry);
}

void
Topology::makeLink(Network* net, SwitchID src, SwitchID dest,
                   std::vector<NetDest>& routing_table_entry)
{
    assert(src >= 2 * m_nodes || dest >= 2 * m_nodes);
    auto links = m_link_map[{src, dest}];

    for (const auto& entry : links) {
        BasicLink* link = entry.link;
        if (src < m_nodes) {
            net->makeExtInLink(src, dest - (2 * m_nodes), link,
                               routing_table_entry);
        } else if (dest < 2 * m_nodes) {
            assert(dest >= m_nodes);
            net->makeExtOutLink(src - (2 * m_nodes), dest - m_nodes, link,
                                routing_table_entry);
        } else {
            net->makeInternalLink(src - (2 * m_nodes), dest - (2 * m_nodes),
                                  link, routing_table_entry,
                                  entry.src_outport_dirn,
                                  entry.dst_inport_dirn);
        }
    }
}

void
Topology::extend_shortest_path(Matrix& current_dist, Matrix& latencies,
                               Matrix& inter_switches)
{
    const int nodes = current_dist[0].size();
    for (uint32_t v = 0; v < m_vnets; v++) {
        for (int k = 0; k < nodes; k++) {
            for (int i = 0; i < nodes; i++) {
                const int dist_i_k = current_dist[v][i][k];
                if (dist_i_k >= infinite_latency) {
                    continue;
                }
                for (int j = 0; j < nodes; j++) {
                    const int dist_k_j = current_dist[v][k][j];
                    if (dist_k_j >= infinite_latency) {
                        continue;
                    }
                    const int candidate = dist_i_k + dist_k_j;
                    if (candidate < current_dist[v][i][j]) {
                        current_dist[v][i][j] = candidate;
                        inter_switches[i][j][v] =
                            inter_switches[i][k][v] +
                            inter_switches[k][j][v] + 1;
                        latencies[i][j][v] =
                            latencies[i][k][v] + latencies[k][j][v];
                    }
                }
            }
        }
    }
}

Matrix
Topology::shortest_path(const Matrix& weights, Matrix& latencies,
                        Matrix& inter_switches)
{
    Matrix dist = weights;
    extend_shortest_path(dist, latencies, inter_switches);
    return dist;
}

bool
Topology::link_is_shortest_path_to_node(SwitchID src, SwitchID next,
                                        SwitchID final,
                                        const Matrix& weights,
                                        const Matrix& dist, int vnet)
{
    return weights[vnet][src][next] + dist[vnet][next][final] ==
           dist[vnet][src][final];
}

NetDest
Topology::shortest_path_to_node(SwitchID src, SwitchID next,
                                const Matrix& weights, const Matrix& dist,
                                int vnet)
{
    NetDest result;
    for (NodeID node = 0; node < static_cast<NodeID>(m_nodes); node++) {
        if (link_is_shortest_path_to_node(src, next, node + m_nodes, weights,
                                          dist, vnet)) {
            result.add(node);
        }
    }
    return result;
}

} // namespace ruby
} // namespace gem5
