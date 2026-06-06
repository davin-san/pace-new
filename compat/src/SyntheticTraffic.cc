#include "pace_compat/SyntheticTraffic.hh"

#include <algorithm>
#include <cmath>
#include <stdexcept>

#include "mem/ruby/slicc_interface/Message.hh"
#include "pace_compat/Json.hh"
#include "pace_compat/Trace.hh"

namespace pace
{

namespace
{

int
pow10Int(int precision)
{
    int value = 1;
    for (int i = 0; i < precision; i++) {
        value *= 10;
    }
    return value;
}

int
asInt(const Json& obj, const std::string& key, int fallback = 0)
{
    return obj.contains(key) ? static_cast<int>(obj.at(key).number()) :
                               fallback;
}

uint64_t
asU64(const Json& obj, const std::string& key, uint64_t fallback = 0)
{
    return obj.contains(key) ? static_cast<uint64_t>(obj.at(key).number()) :
                               fallback;
}

int
ceilDiv(int value, int divisor)
{
    return (value + divisor - 1) / divisor;
}

} // namespace

SyntheticTraffic::SyntheticTraffic(RuntimeNetwork& runtime,
                                   SyntheticTrafficConfig config)
    : _runtime(runtime), _config(std::move(config)),
      _traffic(parseTraffic(_config.synthetic)),
      _sent_by_source(runtime.request_nodes, 0),
      _rng(static_cast<uint32_t>(_config.seed))
{
    _stats.injected_by_vnet.assign(runtime.virtual_networks, 0);
    _stats.delivered_by_vnet.assign(runtime.virtual_networks, 0);
    _stats.injected_flits_by_vnet.assign(runtime.virtual_networks, 0);
    _stats.delivered_flits_by_vnet.assign(runtime.virtual_networks, 0);
}

void
SyntheticTraffic::step(uint64_t cycle)
{
    _stats.cycles = cycle + 1;
    for (int source = 0; source < _runtime.request_nodes; source++) {
        injectForSource(source);
    }
    collectDelivered(cycle);
}

void
SyntheticTraffic::drain(uint64_t cycle)
{
    _stats.cycles = cycle + 1;
    collectDelivered(cycle);
}

void
SyntheticTraffic::injectForSource(int source)
{
    const int inj_range = pow10Int(_config.precision);
    std::uniform_int_distribution<int> should_send(0, inj_range);
    if (should_send(_rng) >= _config.injectionrate * inj_range) {
        return;
    }

    if (_config.num_packets_max >= 0 &&
        _sent_by_source[source] >= _config.num_packets_max) {
        return;
    }

    if (_config.single_sender_id >= 0 &&
        source != _config.single_sender_id) {
        return;
    }

    _stats.attempted++;
    const int destination = chooseDestination(source);
    const int vnet = chooseVnet();
    if (traceEnabled()) {
        traceEvent("traffic.inject_attempt", {
            {"source", traceValue(source)},
            {"destination", traceValue(destination)},
            {"dest_node", traceValue(_runtime.request_nodes + destination)},
            {"vnet", traceValue(vnet)},
        });
    }
    injectMessage(source, destination, vnet);
    _sent_by_source[source]++;
    _stats.injected++;
}

void
SyntheticTraffic::injectMessage(int source, int destination, int vnet)
{
    gem5::ruby::NetDest dest;
    dest.add(_runtime.request_nodes + destination);
    auto msg = std::make_shared<gem5::ruby::Message>(
        dest, messageSizeForVnet(vnet), gem5::curTick());
    if (traceEnabled()) {
        traceEvent("traffic.inject", {
            {"source", traceValue(source)},
            {"destination", traceValue(destination)},
            {"dest_node", traceValue(_runtime.request_nodes + destination)},
            {"vnet", traceValue(vnet)},
            {"message_size", traceValue(messageSizeForVnet(vnet))},
            {"flits", traceValue(flitsForMessage(vnet))},
        });
    }
    _runtime.to_net[source][vnet]->enqueue(msg, gem5::curTick(), 0, nullptr);
    _stats.injected_by_vnet[vnet]++;
    _stats.injected_flits += flitsForMessage(vnet);
    _stats.injected_flits_by_vnet[vnet] += flitsForMessage(vnet);
}

void
SyntheticTraffic::collectDelivered(uint64_t cycle)
{
    const auto now = static_cast<gem5::Tick>(cycle);
    const int first_dir = _runtime.request_nodes;
    const int last_dir = first_dir + _runtime.directory_nodes;
    for (int node = first_dir; node < last_dir; node++) {
        for (int vnet = 0; vnet < _runtime.virtual_networks; vnet++) {
            auto* buffer = _runtime.from_net[node][vnet];
            while (buffer->isReady(now)) {
                auto msg = buffer->peekMsgPtr();
                const int message_size = msg->getMessageSize();
                const uint64_t latency =
                    static_cast<uint64_t>(now - msg->getCreationTime());
                if (traceEnabled()) {
                    traceEvent("traffic.deliver", {
                        {"node", traceValue(node)},
                        {"vnet", traceValue(vnet)},
                        {"message_size", traceValue(message_size)},
                        {"flits", traceValue(flitsForMessage(vnet))},
                        {"latency", traceValue(latency)},
                    });
                }
                buffer->dequeueMsg(now);
                _stats.delivered++;
                _stats.packet_latency_sum += latency;
                _stats.packet_latencies.push_back(latency);
                _stats.delivered_by_vnet[vnet]++;
                _stats.delivered_flits += flitsForMessage(vnet);
                _stats.delivered_flits_by_vnet[vnet] += flitsForMessage(vnet);
            }
        }
    }
}

int
SyntheticTraffic::chooseDestination(int source)
{
    const int num_destinations = _runtime.directory_nodes;
    const int radix = static_cast<int>(std::sqrt(num_destinations));
    const int src_x = radix > 0 ? source % radix : 0;
    const int src_y = radix > 0 ? source / radix : 0;

    if (_config.single_dest_id >= 0) {
        return _config.single_dest_id;
    }

    switch (_traffic) {
      case TrafficType::uniform_random: {
        std::uniform_int_distribution<int> dist(0, num_destinations - 1);
        return dist(_rng);
      }
      case TrafficType::bit_complement: {
        int dest_x = radix - src_x - 1;
        int dest_y = radix - src_y - 1;
        return dest_y * radix + dest_x;
      }
      case TrafficType::bit_reverse: {
        unsigned straight = static_cast<unsigned>(source);
        unsigned reverse = source & 1;
        int num_bits = static_cast<int>(std::log2(num_destinations));
        for (int i = 1; i < num_bits; i++) {
            reverse <<= 1;
            straight >>= 1;
            reverse |= straight & 1;
        }
        return static_cast<int>(reverse);
      }
      case TrafficType::bit_rotation:
        if (source % 2 == 0) {
            return source / 2;
        }
        return source / 2 + num_destinations / 2;
      case TrafficType::neighbor:
        return src_y * radix + ((src_x + 1) % radix);
      case TrafficType::shuffle:
        if (source < num_destinations / 2) {
            return source * 2;
        }
        return source * 2 - num_destinations + 1;
      case TrafficType::transpose:
        return src_x * radix + src_y;
      case TrafficType::tornado:
        return src_y * radix +
               ((src_x + static_cast<int>(std::ceil(radix / 2.0)) - 1) %
                radix);
    }
    return 0;
}

int
SyntheticTraffic::chooseVnet()
{
    if (_config.inj_vnet >= 0 && _config.inj_vnet < _runtime.virtual_networks) {
        return _config.inj_vnet;
    }
    const int max_vnet = std::min(2, _runtime.virtual_networks - 1);
    std::uniform_int_distribution<int> dist(0, max_vnet);
    return dist(_rng);
}

SyntheticTraffic::TrafficType
SyntheticTraffic::parseTraffic(const std::string& name) const
{
    if (name == "bit_complement") return TrafficType::bit_complement;
    if (name == "bit_reverse") return TrafficType::bit_reverse;
    if (name == "bit_rotation") return TrafficType::bit_rotation;
    if (name == "neighbor") return TrafficType::neighbor;
    if (name == "shuffle") return TrafficType::shuffle;
    if (name == "tornado") return TrafficType::tornado;
    if (name == "transpose") return TrafficType::transpose;
    if (name == "uniform_random") return TrafficType::uniform_random;
    throw std::runtime_error("unknown synthetic traffic type: " + name);
}

int
SyntheticTraffic::messageSizeForVnet(int vnet) const
{
    return vnet == 2 ? 72 : 8;
}

int
SyntheticTraffic::flitsForMessage(int vnet) const
{
    const int width = static_cast<int>(_runtime.network->getNiFlitSize());
    return static_cast<int>(std::ceil(
        static_cast<double>(messageSizeForVnet(vnet)) / width));
}

ReplayTrafficConfig
loadReplayTrafficConfig(const std::string& replay_json,
                        uint64_t drain_override)
{
    ReplayTrafficConfig config;
    Json root = parseJsonFile(replay_json);
    config.sim_cycles = asU64(root, "sim_cycles", config.sim_cycles);
    config.drain_cycles = drain_override > 0 ?
        drain_override : asU64(root, "drain_cycles", config.drain_cycles);
    for (const auto& packet_json : root.at("packets").array()) {
        ReplayPacket packet;
        packet.cycle = asU64(packet_json, "cycle");
        packet.source = asInt(packet_json, "source");
        packet.destination = asInt(packet_json, "destination");
        packet.vnet = asInt(packet_json, "vnet");
        packet.message_size = asInt(packet_json, "message_size");
        packet.flits = asInt(packet_json, "flits");
        config.packets.push_back(packet);
    }
    std::stable_sort(config.packets.begin(), config.packets.end(),
        [](const ReplayPacket& lhs, const ReplayPacket& rhs) {
            return lhs.cycle < rhs.cycle;
        });
    if (config.sim_cycles == 0 && !config.packets.empty()) {
        config.sim_cycles = config.packets.back().cycle + 1;
    }
    return config;
}

ReplayTraffic::ReplayTraffic(RuntimeNetwork& runtime,
                             ReplayTrafficConfig config)
    : _runtime(runtime), _config(std::move(config))
{
    _stats.injected_by_vnet.assign(runtime.virtual_networks, 0);
    _stats.delivered_by_vnet.assign(runtime.virtual_networks, 0);
    _stats.injected_flits_by_vnet.assign(runtime.virtual_networks, 0);
    _stats.delivered_flits_by_vnet.assign(runtime.virtual_networks, 0);
}

void
ReplayTraffic::step(uint64_t cycle)
{
    _stats.cycles = cycle + 1;
    while (_next_packet < _config.packets.size() &&
           _config.packets[_next_packet].cycle == cycle) {
        inject(_config.packets[_next_packet]);
        _next_packet++;
    }
    collectDelivered(cycle);
}

void
ReplayTraffic::drain(uint64_t cycle)
{
    _stats.cycles = cycle + 1;
    collectDelivered(cycle);
}

void
ReplayTraffic::inject(const ReplayPacket& packet)
{
    if (packet.source < 0 || packet.source >= _runtime.nodes ||
        packet.destination < 0 || packet.destination >= _runtime.nodes ||
        packet.vnet < 0 || packet.vnet >= _runtime.virtual_networks) {
        throw std::runtime_error("replay packet has invalid endpoint or vnet");
    }
    const int flit_size = static_cast<int>(_runtime.network->getNiFlitSize());
    const int message_size = packet.message_size > 0 ?
        packet.message_size : packet.flits * flit_size;
    const int flits = packet.flits > 0 ?
        packet.flits : ceilDiv(message_size, flit_size);

    gem5::ruby::NetDest dest;
    dest.add(packet.destination);
    auto msg = std::make_shared<gem5::ruby::Message>(
        dest, message_size, gem5::curTick());
    if (traceEnabled()) {
        traceEvent("replay.inject", {
            {"source", traceValue(packet.source)},
            {"destination", traceValue(packet.destination)},
            {"vnet", traceValue(packet.vnet)},
            {"message_size", traceValue(message_size)},
            {"flits", traceValue(flits)},
        });
    }
    _runtime.to_net[packet.source][packet.vnet]->enqueue(
        msg, gem5::curTick(), 0, nullptr);
    _stats.attempted++;
    _stats.injected++;
    _stats.injected_by_vnet[packet.vnet]++;
    _stats.injected_flits += flits;
    _stats.injected_flits_by_vnet[packet.vnet] += flits;
}

void
ReplayTraffic::collectDelivered(uint64_t cycle)
{
    const auto now = static_cast<gem5::Tick>(cycle);
    const int flit_size = static_cast<int>(_runtime.network->getNiFlitSize());
    for (int node = 0; node < _runtime.nodes; node++) {
        for (int vnet = 0; vnet < _runtime.virtual_networks; vnet++) {
            auto* buffer = _runtime.from_net[node][vnet];
            while (buffer->isReady(now)) {
                auto msg = buffer->peekMsgPtr();
                const int message_size = msg->getMessageSize();
                const uint64_t latency =
                    static_cast<uint64_t>(now - msg->getCreationTime());
                const int flits = ceilDiv(message_size, flit_size);
                if (traceEnabled()) {
                    traceEvent("replay.deliver", {
                        {"node", traceValue(node)},
                        {"vnet", traceValue(vnet)},
                        {"message_size", traceValue(message_size)},
                        {"flits", traceValue(flits)},
                        {"latency", traceValue(latency)},
                    });
                }
                buffer->dequeueMsg(now);
                _stats.delivered++;
                _stats.packet_latency_sum += latency;
                _stats.packet_latencies.push_back(latency);
                _stats.delivered_by_vnet[vnet]++;
                _stats.delivered_flits += flits;
                _stats.delivered_flits_by_vnet[vnet] += flits;
            }
        }
    }
}

} // namespace pace
