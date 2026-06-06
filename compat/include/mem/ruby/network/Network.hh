#ifndef __PACE_COMPAT_NETWORK_HH__
#define __PACE_COMPAT_NETWORK_HH__

#include <string>
#include <vector>

#include "mem/ruby/network/BasicLink.hh"
#include "mem/ruby/network/MessageBuffer.hh"
#include "mem/ruby/network/Topology.hh"
#include "pace_compat/Stats.hh"
#include "params/Network.hh"
#include "sim/clocked_object.hh"

namespace gem5
{
namespace ruby
{

class Network : public ClockedObject
{
  public:
    typedef NetworkParams Params;
    explicit Network(const Params& p);
    const Params& params() const { return _params; }

    void init() override {}
    void regStats() override {}

    NodeID getLocalNodeID(NodeID id) const { return id; }
    int MessageSizeType_to_int(int size) const { return size; }
    bool getRandomization() const { return false; }
    bool getWarmupEnabled() const { return false; }
    RubySystem* getRubySystem() const { return _params.ruby_system; }
    int getNumNodes() const { return m_nodes; }
    int getNumVnets() const { return m_virtual_networks; }

    void setNodeBuffers(
        const std::vector<std::vector<MessageBuffer*>>& to_net,
        const std::vector<std::vector<MessageBuffer*>>& from_net)
    {
        m_toNetQueues = to_net;
        m_fromNetQueues = from_net;
    }

    std::vector<std::vector<MessageBuffer*>>& toNetQueues()
    {
        return m_toNetQueues;
    }

    std::vector<std::vector<MessageBuffer*>>& fromNetQueues()
    {
        return m_fromNetQueues;
    }

    virtual void makeExtOutLink(SwitchID, NodeID, BasicLink*,
                                std::vector<NetDest>&) {}
    virtual void makeExtInLink(NodeID, SwitchID, BasicLink*,
                               std::vector<NetDest>&) {}
    virtual void makeInternalLink(SwitchID, SwitchID, BasicLink*,
                                  std::vector<NetDest>&, PortDirection,
                                  PortDirection) {}

  protected:
    int m_virtual_networks;
    int m_nodes;
    std::vector<bool> m_ordered;
    std::vector<std::string> m_vnet_type_names;
    Topology* m_topology_ptr;
    std::vector<std::vector<MessageBuffer*>> m_toNetQueues;
    std::vector<std::vector<MessageBuffer*>> m_fromNetQueues;

  private:
    Params _params;
};

} // namespace ruby
} // namespace gem5

#endif // __PACE_COMPAT_NETWORK_HH__
