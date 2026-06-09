#ifndef __PACE_COMPAT_RUNTIME_NETWORK_HH__
#define __PACE_COMPAT_RUNTIME_NETWORK_HH__

#include <memory>
#include <string>
#include <vector>

#include "mem/ruby/network/Topology.hh"
#include "mem/ruby/network/MessageBuffer.hh"
#include "mem/ruby/network/garnet/GarnetLink.hh"
#include "mem/ruby/network/garnet/GarnetNetwork.hh"
#include "mem/ruby/network/garnet/NetworkBridge.hh"
#include "mem/ruby/network/garnet/NetworkInterface.hh"
#include "mem/ruby/network/garnet/NetworkLink.hh"
#include "mem/ruby/network/garnet/Router.hh"
#include "mem/ruby/system/RubySystem.hh"

namespace pace
{

struct RuntimeNetwork
{
    std::unique_ptr<gem5::ruby::RubySystem> ruby_system;
    std::unique_ptr<gem5::ruby::Topology> topology;
    std::unique_ptr<gem5::ruby::garnet::GarnetNetwork> network;

    std::vector<std::unique_ptr<gem5::ruby::garnet::Router>> routers;
    std::vector<std::unique_ptr<gem5::ruby::garnet::NetworkInterface>> netifs;
    std::vector<std::unique_ptr<gem5::ruby::garnet::NetworkLink>> network_links;
    std::vector<std::unique_ptr<gem5::ruby::garnet::CreditLink>> credit_links;
    std::vector<std::unique_ptr<gem5::ruby::garnet::NetworkBridge>> bridges;
    std::vector<std::unique_ptr<gem5::ruby::garnet::GarnetExtLink>> ext_links;
    std::vector<std::unique_ptr<gem5::ruby::garnet::GarnetIntLink>> int_links;
    std::vector<std::vector<std::unique_ptr<gem5::ruby::MessageBuffer>>>
        to_net_storage;
    std::vector<std::vector<std::unique_ptr<gem5::ruby::MessageBuffer>>>
        from_net_storage;
    std::vector<std::vector<gem5::ruby::MessageBuffer*>> to_net;
    std::vector<std::vector<gem5::ruby::MessageBuffer*>> from_net;

    int nodes = 0;
    int request_nodes = 0;
    int directory_nodes = 0;
    int virtual_networks = 0;
    int max_router_latency = 0;
    int max_link_latency = 0;
    std::vector<bool> vnet_ordered;
    std::vector<std::string> vnet_type_names;
};

RuntimeNetwork instantiateRuntimeNetwork(const std::string& topology_json);

} // namespace pace

#endif // __PACE_COMPAT_RUNTIME_NETWORK_HH__
