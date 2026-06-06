#ifndef __PACE_COMPAT_TOPOLOGY_HH__
#define __PACE_COMPAT_TOPOLOGY_HH__

#include <map>
#include <utility>
#include <vector>

#include "mem/ruby/common/NetDest.hh"

namespace gem5
{
namespace ruby
{

class BasicLink;
class Network;

using Matrix = std::vector<std::vector<std::vector<int>>>;

class Topology
{
  public:
    Topology(uint32_t num_nodes, uint32_t num_routers, uint32_t num_vnets);

    void addExtLink(NodeID node, SwitchID router, BasicLink* link);
    void addIntLink(SwitchID src, SwitchID dest, BasicLink* link,
                    PortDirection src_outport_dirn,
                    PortDirection dst_inport_dirn);
    void createLinks(Network* net);

  private:
    struct LinkEntry {
        BasicLink* link = nullptr;
        PortDirection src_outport_dirn;
        PortDirection dst_inport_dirn;
    };

    using LinkMap =
        std::map<std::pair<SwitchID, SwitchID>, std::vector<LinkEntry>>;

    void addLink(SwitchID src, SwitchID dest, BasicLink* link,
                 PortDirection src_outport_dirn = "",
                 PortDirection dst_inport_dirn = "");
    void makeLink(Network* net, SwitchID src, SwitchID dest,
                  std::vector<NetDest>& routing_table_entry);
    void extend_shortest_path(Matrix& current_dist, Matrix& latencies,
                              Matrix& inter_switches);
    Matrix shortest_path(const Matrix& weights, Matrix& latencies,
                         Matrix& inter_switches);
    bool link_is_shortest_path_to_node(SwitchID src, SwitchID next,
                                       SwitchID final, const Matrix& weights,
                                       const Matrix& dist, int vnet);
    NetDest shortest_path_to_node(SwitchID src, SwitchID next,
                                  const Matrix& weights, const Matrix& dist,
                                  int vnet);

    uint32_t m_nodes;
    uint32_t m_number_of_switches;
    uint32_t m_vnets;
    LinkMap m_link_map;
};

} // namespace ruby
} // namespace gem5

#endif // __PACE_COMPAT_TOPOLOGY_HH__
