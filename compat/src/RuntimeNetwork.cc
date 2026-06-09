#include "pace_compat/RuntimeNetwork.hh"

#include <sstream>
#include <stdexcept>

#include "pace_compat/Json.hh"
#include "pace_compat/Trace.hh"

namespace pace
{

namespace
{

using namespace gem5;
using namespace gem5::ruby;
using namespace gem5::ruby::garnet;

int asInt(const Json& obj, const std::string& key, int fallback = 0)
{
    if (!obj.contains(key)) {
        return fallback;
    }
    return static_cast<int>(obj.at(key).number());
}

bool asBool(const Json& obj, const std::string& key, bool fallback = false)
{
    if (!obj.contains(key)) {
        return fallback;
    }
    return obj.at(key).boolean();
}

std::string asString(const Json& obj, const std::string& key,
                     const std::string& fallback = "")
{
    if (!obj.contains(key)) {
        return fallback;
    }
    return obj.at(key).string();
}

std::vector<int> asIntVector(const Json& obj, const std::string& key)
{
    std::vector<int> out;
    if (!obj.contains(key)) {
        return out;
    }
    for (const auto& item : obj.at(key).array()) {
        out.push_back(static_cast<int>(item.number()));
    }
    return out;
}

std::vector<bool> asBoolVector(const Json& obj, const std::string& key)
{
    std::vector<bool> out;
    if (!obj.contains(key)) {
        return out;
    }
    for (const auto& item : obj.at(key).array()) {
        out.push_back(item.boolean());
    }
    return out;
}

std::vector<std::string> asStringVector(const Json& obj,
                                        const std::string& key)
{
    std::vector<std::string> out;
    if (!obj.contains(key)) {
        return out;
    }
    for (const auto& item : obj.at(key).array()) {
        out.push_back(item.string());
    }
    return out;
}

std::vector<bool> defaultVnetOrdered(int virtual_networks)
{
    return std::vector<bool>(virtual_networks, false);
}

std::vector<std::string> defaultVnetTypeNames(int virtual_networks)
{
    std::vector<std::string> names(virtual_networks, "request");
    if (virtual_networks > 1) {
        names[1] = "response";
    }
    return names;
}

template <class T>
void requireSize(const std::vector<T>& values, int expected,
                 const std::string& field)
{
    if (!values.empty() && static_cast<int>(values.size()) != expected) {
        throw std::runtime_error(field + " has " +
            std::to_string(values.size()) + " entries but network has " +
            std::to_string(expected) + " virtual networks");
    }
}

std::string joinBools(const std::vector<bool>& values)
{
    std::ostringstream out;
    for (size_t i = 0; i < values.size(); i++) {
        if (i != 0) {
            out << ",";
        }
        out << (values[i] ? "true" : "false");
    }
    return out.str();
}

std::string joinStrings(const std::vector<std::string>& values)
{
    std::ostringstream out;
    for (size_t i = 0; i < values.size(); i++) {
        if (i != 0) {
            out << ",";
        }
        out << values[i];
    }
    return out.str();
}

NetworkLinkParams networkLinkParams(const Json& link, const std::string& name,
                                    int id, int virt_nets, int vcs_per_vnet,
                                    uint32_t width)
{
    NetworkLinkParams params;
    params.name = name;
    params.link_id = id;
    params.link_latency = asInt(link, "latency", 1);
    params.vcs_per_vnet = vcs_per_vnet;
    params.virt_nets = virt_nets;
    params.supported_vnets = asIntVector(link, "supported_vnets");
    params.width = width;
    return params;
}

CreditLinkParams creditLinkParams(const Json& link, const std::string& name,
                                  int id, int virt_nets, int vcs_per_vnet,
                                  uint32_t width)
{
    CreditLinkParams params;
    params.name = name;
    params.link_id = id;
    params.link_latency = asInt(link, "latency", 1);
    params.vcs_per_vnet = vcs_per_vnet;
    params.virt_nets = virt_nets;
    params.supported_vnets = asIntVector(link, "supported_vnets");
    params.width = width;
    return params;
}

NetworkBridgeParams bridgeParams(const std::string& name, int id,
                                 NetworkLink* link, int vtype, uint32_t width,
                                 int virt_nets, int vcs_per_vnet)
{
    NetworkBridgeParams params;
    params.name = name;
    params.link_id = id;
    params.link_latency = 1;
    params.vcs_per_vnet = vcs_per_vnet;
    params.virt_nets = virt_nets;
    params.width = width;
    params.link = link;
    params.vtype = vtype;
    return params;
}

template <class T, class Params>
T* emplace(std::vector<std::unique_ptr<T>>& storage, const Params& params)
{
    storage.push_back(std::make_unique<T>(params));
    return storage.back().get();
}

} // namespace

RuntimeNetwork
instantiateRuntimeNetwork(const std::string& topology_json)
{
    Json root = parseJsonFile(topology_json);
    const Json& net = root.contains("network") ? root.at("network") : root;

    RuntimeNetwork runtime;
    runtime.ruby_system = std::make_unique<RubySystem>();
    runtime.nodes = static_cast<int>(net.at("controllers").array().size());
    runtime.virtual_networks = asInt(net, "number_of_virtual_networks", 3);
    const int vcs_per_vnet = asInt(net, "vcs_per_vnet", 4);
    const uint32_t ni_flit_size =
        static_cast<uint32_t>(asInt(net, "ni_flit_size", 16));
    traceEvent("runtime.network_config", {
        {"nodes", traceValue(runtime.nodes)},
        {"virtual_networks", traceValue(runtime.virtual_networks)},
        {"vcs_per_vnet", traceValue(vcs_per_vnet)},
        {"ni_flit_size", traceValue(ni_flit_size)},
        {"routing_algorithm", traceValue(asInt(net, "routing_algorithm", 0))},
        {"mesh_rows", traceValue(asInt(net, "mesh_rows", 0))},
    });
    for (const auto& controller_json : net.at("controllers").array()) {
        std::string type = asString(controller_json, "type");
        if (type == "L1Cache_Controller") {
            runtime.request_nodes++;
        } else if (type == "Directory_Controller") {
            runtime.directory_nodes++;
        }
    }
    if (runtime.directory_nodes == 0) {
        runtime.directory_nodes = runtime.nodes - runtime.request_nodes;
    }
    traceEvent("runtime.controller_counts", {
        {"request_nodes", traceValue(runtime.request_nodes)},
        {"directory_nodes", traceValue(runtime.directory_nodes)},
    });

    for (const auto& router_json : net.at("routers").array()) {
        GarnetRouterParams params;
        params.name = "router" + std::to_string(asInt(router_json, "router_id"));
        params.router_id = asInt(router_json, "router_id");
        params.latency = asInt(router_json, "latency", 1);
        params.virt_nets = runtime.virtual_networks;
        params.vcs_per_vnet = vcs_per_vnet;
        params.width = static_cast<uint32_t>(asInt(router_json, "width",
                                                   ni_flit_size));
        runtime.max_router_latency = std::max(
            runtime.max_router_latency, static_cast<int>(params.latency));
        emplace(runtime.routers, params);
        traceEvent("runtime.router", {
            {"router_id", traceValue(params.router_id)},
            {"latency", traceValue(params.latency)},
            {"width", traceValue(params.width)},
        });
    }

    for (int i = 0; i < runtime.nodes; i++) {
        GarnetNetworkInterfaceParams params;
        params.name = "network_interface" + std::to_string(i);
        params.id = i;
        params.virt_nets = runtime.virtual_networks;
        params.garnet_deadlock_threshold =
            asInt(net, "garnet_deadlock_threshold", 50000);
        emplace(runtime.netifs, params);
        traceEvent("runtime.network_interface", {
            {"node", traceValue(i)},
            {"virtual_networks", traceValue(params.virt_nets)},
            {"deadlock_threshold",
             traceValue(params.garnet_deadlock_threshold)},
        });
    }

    runtime.to_net_storage.resize(runtime.nodes);
    runtime.from_net_storage.resize(runtime.nodes);
    runtime.to_net.resize(runtime.nodes);
    runtime.from_net.resize(runtime.nodes);
    for (int node = 0; node < runtime.nodes; node++) {
        runtime.to_net_storage[node].resize(runtime.virtual_networks);
        runtime.from_net_storage[node].resize(runtime.virtual_networks);
        runtime.to_net[node].resize(runtime.virtual_networks);
        runtime.from_net[node].resize(runtime.virtual_networks);
        for (int vnet = 0; vnet < runtime.virtual_networks; vnet++) {
            runtime.to_net_storage[node][vnet] =
                std::make_unique<MessageBuffer>();
            runtime.from_net_storage[node][vnet] =
                std::make_unique<MessageBuffer>();
            runtime.to_net[node][vnet] = runtime.to_net_storage[node][vnet].get();
            runtime.from_net[node][vnet] =
                runtime.from_net_storage[node][vnet].get();
        }
    }

    runtime.topology = std::make_unique<Topology>(
        runtime.nodes, static_cast<uint32_t>(runtime.routers.size()),
        runtime.virtual_networks);

    for (const auto& link_json : net.at("ext_links").array()) {
        const int link_id = asInt(link_json, "link_id");
        const uint32_t width =
            static_cast<uint32_t>(asInt(link_json, "width", ni_flit_size));

        NetworkLink* in_net = emplace(
            runtime.network_links,
            networkLinkParams(link_json, "ext_in_net" + std::to_string(link_id),
                              link_id, runtime.virtual_networks, vcs_per_vnet,
                              width));
        NetworkLink* out_net = emplace(
            runtime.network_links,
            networkLinkParams(link_json,
                              "ext_out_net" + std::to_string(link_id),
                              link_id, runtime.virtual_networks, vcs_per_vnet,
                              width));
        CreditLink* in_credit = emplace(
            runtime.credit_links,
            creditLinkParams(link_json,
                             "ext_in_credit" + std::to_string(link_id),
                             link_id, runtime.virtual_networks, vcs_per_vnet,
                             width));
        CreditLink* out_credit = emplace(
            runtime.credit_links,
            creditLinkParams(link_json,
                             "ext_out_credit" + std::to_string(link_id),
                             link_id, runtime.virtual_networks, vcs_per_vnet,
                             width));

        GarnetExtLinkParams params;
        params.name = "ext_link" + std::to_string(link_id);
        params.latency = asInt(link_json, "latency", 1);
        params.bandwidth_factor = asInt(link_json, "bandwidth_factor", 16);
        params.weight = asInt(link_json, "weight", 1);
        runtime.max_link_latency = std::max(
            runtime.max_link_latency, static_cast<int>(params.latency));
        params.supported_vnets = asIntVector(link_json, "supported_vnets");
        params.network_links = {in_net, out_net};
        params.credit_links = {in_credit, out_credit};
        params.ext_cdc = asBool(link_json, "ext_cdc");
        params.int_cdc = asBool(link_json, "int_cdc");
        params.ext_serdes = asBool(link_json, "ext_serdes");
        params.int_serdes = asBool(link_json, "int_serdes");

        const int router_id = asInt(link_json, "int_node");
        const uint32_t router_width = runtime.routers.at(router_id)->getBitWidth();

        if (params.ext_cdc || params.ext_serdes) {
            params.ext_net_bridge = {
                emplace(runtime.bridges,
                        bridgeParams("ext_in_net_bridge" + std::to_string(link_id),
                                     link_id, in_net, enums::OBJECT_LINK, width,
                                     runtime.virtual_networks, vcs_per_vnet)),
                emplace(runtime.bridges,
                        bridgeParams("ext_out_net_bridge" + std::to_string(link_id),
                                     link_id, out_net, enums::LINK_OBJECT, width,
                                     runtime.virtual_networks, vcs_per_vnet)),
            };
            params.ext_cred_bridge = {
                emplace(runtime.bridges,
                        bridgeParams("ext_in_cred_bridge" + std::to_string(link_id),
                                     link_id, in_credit, enums::LINK_OBJECT,
                                     width, runtime.virtual_networks,
                                     vcs_per_vnet)),
                emplace(runtime.bridges,
                        bridgeParams("ext_out_cred_bridge" + std::to_string(link_id),
                                     link_id, out_credit, enums::OBJECT_LINK,
                                     width, runtime.virtual_networks,
                                     vcs_per_vnet)),
            };
        }

        if (params.int_cdc || params.int_serdes) {
            params.int_net_bridge = {
                emplace(runtime.bridges,
                        bridgeParams("int_in_net_bridge" + std::to_string(link_id),
                                     link_id, in_net, enums::LINK_OBJECT,
                                     router_width, runtime.virtual_networks,
                                     vcs_per_vnet)),
                emplace(runtime.bridges,
                        bridgeParams("int_out_net_bridge" + std::to_string(link_id),
                                     link_id, out_net, enums::OBJECT_LINK,
                                     router_width, runtime.virtual_networks,
                                     vcs_per_vnet)),
            };
            params.int_cred_bridge = {
                emplace(runtime.bridges,
                        bridgeParams("int_in_cred_bridge" + std::to_string(link_id),
                                     link_id, in_credit, enums::OBJECT_LINK,
                                     router_width, runtime.virtual_networks,
                                     vcs_per_vnet)),
                emplace(runtime.bridges,
                        bridgeParams("int_out_cred_bridge" + std::to_string(link_id),
                                     link_id, out_credit, enums::LINK_OBJECT,
                                     router_width, runtime.virtual_networks,
                                     vcs_per_vnet)),
            };
        }

        GarnetExtLink* ext_link = emplace(runtime.ext_links, params);
        ext_link->init();
        traceEvent("runtime.ext_link", {
            {"link_id", traceValue(link_id)},
            {"ext_node", traceValue(asInt(link_json, "ext_node"))},
            {"int_node", traceValue(asInt(link_json, "int_node"))},
            {"latency", traceValue(params.latency)},
            {"weight", traceValue(params.weight)},
            {"width", traceValue(width)},
            {"ext_cdc", traceValue(params.ext_cdc)},
            {"int_cdc", traceValue(params.int_cdc)},
            {"ext_serdes", traceValue(params.ext_serdes)},
            {"int_serdes", traceValue(params.int_serdes)},
        });
        runtime.topology->addExtLink(asInt(link_json, "ext_node"),
                                     asInt(link_json, "int_node"), ext_link);
    }

    for (const auto& link_json : net.at("int_links").array()) {
        const int link_id = asInt(link_json, "link_id");
        const int src = asInt(link_json, "src_node");
        const int dst = asInt(link_json, "dst_node");
        const uint32_t width =
            static_cast<uint32_t>(asInt(link_json, "width", ni_flit_size));

        NetworkLink* net_link = emplace(
            runtime.network_links,
            networkLinkParams(link_json, "int_net" + std::to_string(link_id),
                              link_id, runtime.virtual_networks, vcs_per_vnet,
                              width));
        CreditLink* credit_link = emplace(
            runtime.credit_links,
            creditLinkParams(link_json, "int_credit" + std::to_string(link_id),
                             link_id, runtime.virtual_networks, vcs_per_vnet,
                             width));

        GarnetIntLinkParams params;
        params.name = "int_link" + std::to_string(link_id);
        params.latency = asInt(link_json, "latency", 1);
        params.bandwidth_factor = asInt(link_json, "bandwidth_factor", 16);
        params.weight = asInt(link_json, "weight", 1);
        runtime.max_link_latency = std::max(
            runtime.max_link_latency, static_cast<int>(params.latency));
        params.supported_vnets = asIntVector(link_json, "supported_vnets");
        params.network_link = net_link;
        params.credit_link = credit_link;
        params.src_cdc = asBool(link_json, "src_cdc");
        params.dst_cdc = asBool(link_json, "dst_cdc");
        params.src_serdes = asBool(link_json, "src_serdes");
        params.dst_serdes = asBool(link_json, "dst_serdes");

        const uint32_t src_width = runtime.routers.at(src)->getBitWidth();
        const uint32_t dst_width = runtime.routers.at(dst)->getBitWidth();
        if (params.src_cdc || params.src_serdes) {
            params.src_net_bridge = emplace(
                runtime.bridges,
                bridgeParams("src_net_bridge" + std::to_string(link_id),
                             link_id, net_link, enums::OBJECT_LINK, src_width,
                             runtime.virtual_networks, vcs_per_vnet));
            params.src_cred_bridge = emplace(
                runtime.bridges,
                bridgeParams("src_cred_bridge" + std::to_string(link_id),
                             link_id, credit_link, enums::LINK_OBJECT,
                             src_width, runtime.virtual_networks, vcs_per_vnet));
        }
        if (params.dst_cdc || params.dst_serdes) {
            params.dst_net_bridge = emplace(
                runtime.bridges,
                bridgeParams("dst_net_bridge" + std::to_string(link_id),
                             link_id, net_link, enums::LINK_OBJECT, dst_width,
                             runtime.virtual_networks, vcs_per_vnet));
            params.dst_cred_bridge = emplace(
                runtime.bridges,
                bridgeParams("dst_cred_bridge" + std::to_string(link_id),
                             link_id, credit_link, enums::OBJECT_LINK,
                             dst_width, runtime.virtual_networks, vcs_per_vnet));
        }

        GarnetIntLink* int_link = emplace(runtime.int_links, params);
        int_link->init();
        traceEvent("runtime.int_link", {
            {"link_id", traceValue(link_id)},
            {"src_node", traceValue(src)},
            {"dst_node", traceValue(dst)},
            {"src_outport", traceValue(asString(link_json, "src_outport"))},
            {"dst_inport", traceValue(asString(link_json, "dst_inport"))},
            {"latency", traceValue(params.latency)},
            {"weight", traceValue(params.weight)},
            {"width", traceValue(width)},
            {"src_cdc", traceValue(params.src_cdc)},
            {"dst_cdc", traceValue(params.dst_cdc)},
            {"src_serdes", traceValue(params.src_serdes)},
            {"dst_serdes", traceValue(params.dst_serdes)},
        });
        runtime.topology->addIntLink(src, dst, int_link,
                                     asString(link_json, "src_outport"),
                                     asString(link_json, "dst_inport"));
    }

    GarnetNetworkParams net_params;
    net_params.name = "garnet_network";
    net_params.number_of_virtual_networks = runtime.virtual_networks;
    net_params.number_of_nodes = runtime.nodes;
    net_params.vnet_ordered = asBoolVector(net, "vnet_ordered");
    requireSize(net_params.vnet_ordered, runtime.virtual_networks,
                "vnet_ordered");
    if (net_params.vnet_ordered.empty()) {
        net_params.vnet_ordered = defaultVnetOrdered(runtime.virtual_networks);
    }
    net_params.vnet_type_names = asStringVector(net, "vnet_type_names");
    requireSize(net_params.vnet_type_names, runtime.virtual_networks,
                "vnet_type_names");
    if (net_params.vnet_type_names.empty()) {
        net_params.vnet_type_names =
            defaultVnetTypeNames(runtime.virtual_networks);
    }
    runtime.vnet_ordered = net_params.vnet_ordered;
    runtime.vnet_type_names = net_params.vnet_type_names;
    net_params.topology = runtime.topology.get();
    net_params.ruby_system = runtime.ruby_system.get();
    net_params.num_rows = asInt(net, "mesh_rows", 0);
    net_params.ni_flit_size = ni_flit_size;
    net_params.routing_algorithm = asInt(net, "routing_algorithm", 0);
    for (auto& router : runtime.routers) {
        net_params.routers.push_back(router.get());
    }
    for (auto& ni : runtime.netifs) {
        net_params.netifs.push_back(ni.get());
    }
    traceEvent("runtime.vnet_metadata", {
        {"vnet_ordered", traceValue(joinBools(net_params.vnet_ordered))},
        {"vnet_type_names", traceValue(joinStrings(net_params.vnet_type_names))},
    });

    runtime.network = std::make_unique<GarnetNetwork>(net_params);
    runtime.network->setNodeBuffers(runtime.to_net, runtime.from_net);
    runtime.network->init();
    runtime.network->regStats();
    for (auto& router : runtime.routers) {
        router->init();
        router->regStats();
    }
    traceEvent("runtime.instantiated", {
        {"nodes", traceValue(runtime.nodes)},
        {"routers", traceValue(runtime.routers.size())},
        {"netifs", traceValue(runtime.netifs.size())},
        {"ext_links", traceValue(runtime.ext_links.size())},
        {"int_links", traceValue(runtime.int_links.size())},
        {"network_links", traceValue(runtime.network_links.size())},
        {"credit_links", traceValue(runtime.credit_links.size())},
        {"bridges", traceValue(runtime.bridges.size())},
    });

    return runtime;
}

} // namespace pace
