#include "mem/ruby/network/Network.hh"

namespace gem5
{
namespace ruby
{

Network::Network(const Params& p)
    : ClockedObject(p), m_virtual_networks(p.number_of_virtual_networks),
      m_nodes(p.number_of_nodes), m_ordered(p.vnet_ordered),
      m_vnet_type_names(p.vnet_type_names), m_topology_ptr(p.topology),
      _params(p)
{
    m_toNetQueues.resize(m_nodes);
    m_fromNetQueues.resize(m_nodes);
}

} // namespace ruby
} // namespace gem5
