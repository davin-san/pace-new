#include "pace_compat/SyntheticTraffic.hh"

#include <algorithm>
#include <cmath>
#include <map>
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

double
asDouble(const Json& obj, const std::string& key, double fallback = 0.0)
{
    return obj.contains(key) ? obj.at(key).number() : fallback;
}

uint64_t
flowKey(int source, int vnet, int flits)
{
    return (static_cast<uint64_t>(static_cast<uint32_t>(source)) << 32) |
           (static_cast<uint64_t>(static_cast<uint16_t>(vnet)) << 16) |
           static_cast<uint64_t>(static_cast<uint16_t>(flits));
}

int
ceilDiv(int value, int divisor)
{
    return (value + divisor - 1) / divisor;
}

template <class Choice>
const Choice&
weightedChoice(std::mt19937& rng, const std::vector<Choice>& choices)
{
    uint64_t total = 0;
    for (const auto& choice : choices) {
        total += choice.weight;
    }
    if (total == 0) {
        std::uniform_int_distribution<size_t> dist(0, choices.size() - 1);
        return choices[dist(rng)];
    }
    std::uniform_int_distribution<uint64_t> dist(1, total);
    uint64_t target = dist(rng);
    uint64_t acc = 0;
    for (const auto& choice : choices) {
        acc += choice.weight;
        if (target <= acc) {
            return choice;
        }
    }
    return choices.back();
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
                const uint64_t network_latency = msg->hasNetworkLatency() ?
                    static_cast<uint64_t>(msg->getNetworkLatency()) :
                    latency;
                if (traceEnabled()) {
                    traceEvent("traffic.deliver", {
                        {"node", traceValue(node)},
                        {"vnet", traceValue(vnet)},
                        {"message_size", traceValue(message_size)},
                        {"flits", traceValue(flitsForMessage(vnet))},
                        {"latency", traceValue(latency)},
                        {"network_latency", traceValue(network_latency)},
                    });
                }
                buffer->dequeueMsg(now);
                _stats.delivered++;
                _stats.packet_latency_sum += latency;
                _stats.packet_latencies.push_back(latency);
                _stats.packet_latency_samples.push_back({
                    latency, vnet, flitsForMessage(vnet)});
                _stats.packet_network_latency_sum += network_latency;
                _stats.packet_network_latencies.push_back(network_latency);
                _stats.packet_network_latency_samples.push_back({
                    network_latency, vnet, flitsForMessage(vnet)});
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
    if (vnet >= 0 && vnet < static_cast<int>(_runtime.vnet_type_names.size()) &&
        _runtime.vnet_type_names[vnet] == "response") {
        return 72;
    }
    return 8;
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

ProfileTrafficConfig
loadProfileTrafficConfig(const std::string& profile_json,
                         uint64_t sim_cycles_override,
                         uint64_t drain_override, double rate_scale,
                         bool closed_loop, bool bursty, bool phased,
                         bool flow_timing, bool flow_timing_auto)
{
    ProfileTrafficConfig config;
    Json root = parseJsonFile(profile_json);
    const Json& scale = root.at("scale");
    const Json& traffic = root.at("traffic");
    const int num_cpus = root.at("source").contains("num_cpus") ?
        static_cast<int>(root.at("source").at("num_cpus").number()) : 1;
    const uint64_t total_packets = asU64(scale, "total_packets", 0);
    const double lambda_per_cpu = asDouble(scale, "lambda_per_cpu", 0.0);
    config.closed_loop = closed_loop;
    config.bursty = bursty;
    config.phased = phased;
    config.flow_timing = flow_timing;
    config.flow_timing_auto = flow_timing_auto;
    config.profile_lambda_per_cpu = lambda_per_cpu;
    config.source_flit_size = std::max(
        1, asInt(root.at("source"), "ni_flit_size_bytes",
                 config.source_flit_size));
    if (root.contains("mshr")) {
        const auto& mshr = root.at("mshr");
        config.outstanding_limit = asInt(
            mshr, "slots", config.outstanding_limit);
    }

    config.sim_cycles = sim_cycles_override;
    if (config.sim_cycles == 0) {
        config.sim_cycles = asU64(scale, "sim_cycles", 0);
    }
    if (config.sim_cycles == 0) {
        const uint64_t sim_ticks = asU64(scale, "sim_ticks", 0);
        const uint64_t clock_period_ticks =
            asU64(scale, "clock_period_ticks", 0);
        if (sim_ticks > 0 && clock_period_ticks > 0) {
            config.sim_cycles = std::max<uint64_t>(
                1, (sim_ticks + clock_period_ticks / 2) /
                       clock_period_ticks);
        }
    }
    if (config.sim_cycles == 0 && lambda_per_cpu > 0.0 && num_cpus > 0) {
        config.sim_cycles = static_cast<uint64_t>(
            std::ceil(static_cast<double>(total_packets) /
                      (lambda_per_cpu * static_cast<double>(num_cpus))));
    }
    if (config.sim_cycles == 0) {
        config.sim_cycles = std::max<uint64_t>(1, total_packets * 100);
    }
    config.burst_window_cycles = std::max<uint64_t>(
        1, config.sim_cycles / 10);
    if (drain_override > 0) {
        config.drain_cycles = drain_override;
    }

    const uint64_t unphased_sim_cycles = config.sim_cycles;
    std::vector<std::map<int, double>> phase_source_rates;
    std::vector<uint64_t> phase_cycles_by_index;
    std::map<int, double> phase_fraction_packets_by_source;
    if (config.phased && root.contains("phases")) {
        uint64_t phase_start = 0;
        for (const auto& phase : root.at("phases").array()) {
            const uint64_t phase_cycles = asU64(phase, "sim_cycles", 0);
            const uint64_t phase_packets = asU64(
                phase, "total_packets", 0);
            const bool has_phase_pair_counts =
                phase.contains("src_dst_ni_bytes_counts_by_vnet") ||
                phase.contains("src_dst_ni_flits_counts_by_vnet") ||
                phase.contains("src_dst_ni_counts_by_vnet");
            if (phase_cycles == 0 || phase_packets == 0 ||
                (!phase.contains("source_fractions") &&
                 !has_phase_pair_counts)) {
                continue;
            }
            std::map<int, double> fractions;
            double fraction_sum = 0.0;
            if (phase.contains("source_fractions")) {
                for (const auto& [src_key, fraction_json] :
                     phase.at("source_fractions").object()) {
                    const double fraction = fraction_json.number();
                    if (fraction <= 0.0) {
                        continue;
                    }
                    fractions[std::stoi(src_key)] = fraction;
                    fraction_sum += fraction;
                }
            }
            std::map<int, double> rates;
            if (fraction_sum > 0.0) {
                for (const auto& [src, fraction] : fractions) {
                    rates[src] = rate_scale *
                        (static_cast<double>(phase_packets) *
                         (fraction / fraction_sum)) /
                        static_cast<double>(phase_cycles);
                    phase_fraction_packets_by_source[src] +=
                        rates[src] * static_cast<double>(phase_cycles);
                }
            }
            phase_start += phase_cycles;
            config.phase_end_cycles.push_back(phase_start);
            phase_cycles_by_index.push_back(phase_cycles);
            phase_source_rates.push_back(std::move(rates));
        }
        if (!config.phase_end_cycles.empty()) {
            config.sim_cycles = config.phase_end_cycles.back();
        }
    }

    double phase_burst_cv = 0.0;
    std::map<int, double> source_burst_cv;
    std::map<uint64_t, double> flow_interarrival_cv;
    if (root.contains("burst")) {
        const auto& burst = root.at("burst");
        phase_burst_cv = asDouble(burst, "phase_lambda_cv", 0.0);
        if (burst.contains("per_node_injection_cv")) {
            for (const auto& [src_key, cv_json] :
                 burst.at("per_node_injection_cv").object()) {
                source_burst_cv[std::stoi(src_key)] = cv_json.number();
            }
        }
        if (burst.contains("flow_interarrival_by_source_vnet_flits")) {
            for (const auto& [src_key, vnets_json] :
                 burst.at("flow_interarrival_by_source_vnet_flits").object()) {
                const int src = std::stoi(src_key);
                for (const auto& [vnet_key, flits_json] :
                     vnets_json.object()) {
                    const int vnet = std::stoi(vnet_key);
                    for (const auto& [flits_key, stat_json] :
                         flits_json.object()) {
                        const int flits = std::stoi(flits_key);
                        flow_interarrival_cv[flowKey(src, vnet, flits)] =
                            asDouble(stat_json, "cv", 1.0);
                    }
                }
            }
        }
    }

    const bool has_byte_hists = traffic.contains("packet_bytes_by_vnet");
    const auto& flit_hists = has_byte_hists ?
        traffic.at("packet_bytes_by_vnet").object() :
        traffic.at("packet_flits_by_vnet").object();
    int max_vnet = 0;
    for (const auto& [vnet_key, _] : flit_hists) {
        max_vnet = std::max(max_vnet, std::stoi(vnet_key));
    }
    config.flits_by_vnet.resize(max_vnet + 1);
    for (const auto& [vnet_key, hist_json] : flit_hists) {
        const int vnet = std::stoi(vnet_key);
        for (const auto& [size_key, count_json] : hist_json.object()) {
            ProfileFlitChoice choice;
            if (has_byte_hists) {
                choice.message_size = std::stoi(size_key);
                choice.flits = ceilDiv(
                    choice.message_size, config.source_flit_size);
            } else {
                choice.flits = std::stoi(size_key);
                choice.message_size =
                    std::max(1, choice.flits) * config.source_flit_size;
            }
            choice.weight = static_cast<uint64_t>(count_json.number());
            config.flits_by_vnet[vnet].push_back(choice);
        }
    }

    std::map<int, ProfileSourceTraffic> by_source;
    const bool has_joint_pair_bytes =
        traffic.contains("src_dst_ni_bytes_counts_by_vnet");
    const bool has_joint_pair_flits =
        traffic.contains("src_dst_ni_flits_counts_by_vnet");
    const auto& pair_counts = has_joint_pair_bytes ?
        traffic.at("src_dst_ni_bytes_counts_by_vnet").object() :
        (has_joint_pair_flits ?
        traffic.at("src_dst_ni_flits_counts_by_vnet").object() :
        traffic.at("src_dst_ni_counts_by_vnet").object());
    uint64_t response_packets = 0;
    uint64_t request_packets = 0;
    for (const auto& [vnet_key, sources_json] : pair_counts) {
        const int vnet = std::stoi(vnet_key);
        if (vnet >= static_cast<int>(config.flits_by_vnet.size())) {
            config.flits_by_vnet.resize(vnet + 1);
        }
        for (const auto& [src_key, dests_json] : sources_json.object()) {
            const int src = std::stoi(src_key);
            auto& source = by_source[src];
            source.source = src;
            for (const auto& [dst_key, count_json] : dests_json.object()) {
                const int dst = std::stoi(dst_key);
                if (has_joint_pair_bytes || has_joint_pair_flits) {
                    for (const auto& [size_key, size_count_json] :
                         count_json.object()) {
                        const uint64_t count = static_cast<uint64_t>(
                            size_count_json.number());
                        if (vnet == config.response_vnet) {
                            response_packets += count;
                        } else {
                            request_packets += count;
                        }
                        if (config.closed_loop &&
                            vnet == config.response_vnet) {
                            continue;
                        }
                        ProfileEndpointChoice choice;
                        choice.vnet = vnet;
                        choice.destination = dst;
                        if (has_joint_pair_bytes) {
                            choice.message_size = std::stoi(size_key);
                            choice.flits = ceilDiv(
                                choice.message_size, config.source_flit_size);
                        } else {
                            choice.flits = std::stoi(size_key);
                            choice.message_size =
                                std::max(1, choice.flits) *
                                config.source_flit_size;
                        }
                        choice.weight = count;
                        source.endpoints.push_back(choice);
                    }
                } else {
                    const uint64_t count =
                        static_cast<uint64_t>(count_json.number());
                    if (vnet == config.response_vnet) {
                        response_packets += count;
                    } else {
                        request_packets += count;
                    }
                    if (config.closed_loop && vnet == config.response_vnet) {
                        continue;
                    }
                    ProfileEndpointChoice choice;
                    choice.vnet = vnet;
                    choice.destination = dst;
                    choice.weight = count;
                    source.endpoints.push_back(choice);
                }
            }
        }
    }
    std::map<int, std::vector<std::vector<ProfileEndpointChoice>>>
        phase_endpoints_by_source;
    std::map<int, double> phase_endpoint_packets_by_source;
    bool has_phase_endpoint_counts = false;
    if (config.phased && root.contains("phases") &&
        !phase_cycles_by_index.empty()) {
        size_t phase_index = 0;
        for (const auto& phase : root.at("phases").array()) {
            const uint64_t phase_cycles = asU64(phase, "sim_cycles", 0);
            const uint64_t phase_packets = asU64(
                phase, "total_packets", 0);
            const bool has_phase_pair_bytes =
                phase.contains("src_dst_ni_bytes_counts_by_vnet");
            const bool has_phase_pair_flits =
                phase.contains("src_dst_ni_flits_counts_by_vnet");
            const bool has_phase_pair_counts =
                phase.contains("src_dst_ni_counts_by_vnet");
            if (phase_cycles == 0 || phase_packets == 0 ||
                (!phase.contains("source_fractions") &&
                 !has_phase_pair_bytes && !has_phase_pair_flits &&
                 !has_phase_pair_counts)) {
                continue;
            }
            if (phase_index >= phase_cycles_by_index.size()) {
                break;
            }
            if (!has_phase_pair_bytes && !has_phase_pair_flits &&
                !has_phase_pair_counts) {
                phase_index++;
                continue;
            }
            const auto& phase_pair_counts = has_phase_pair_bytes ?
                phase.at("src_dst_ni_bytes_counts_by_vnet").object() :
                (has_phase_pair_flits ?
                 phase.at("src_dst_ni_flits_counts_by_vnet").object() :
                 phase.at("src_dst_ni_counts_by_vnet").object());
            for (const auto& [vnet_key, sources_json] : phase_pair_counts) {
                const int vnet = std::stoi(vnet_key);
                for (const auto& [src_key, dests_json] :
                     sources_json.object()) {
                    const int src = std::stoi(src_key);
                    auto& phases = phase_endpoints_by_source[src];
                    if (phases.size() < phase_cycles_by_index.size()) {
                        phases.resize(phase_cycles_by_index.size());
                    }
                    for (const auto& [dst_key, count_json] :
                         dests_json.object()) {
                        const int dst = std::stoi(dst_key);
                        if (has_phase_pair_bytes || has_phase_pair_flits) {
                            for (const auto& [size_key, size_count_json] :
                                 count_json.object()) {
                                const uint64_t count =
                                    static_cast<uint64_t>(
                                        size_count_json.number());
                                if (count == 0) {
                                    continue;
                                }
                                ProfileEndpointChoice choice;
                                choice.vnet = vnet;
                                choice.destination = dst;
                                if (has_phase_pair_bytes) {
                                    choice.message_size = std::stoi(size_key);
                                    choice.flits = ceilDiv(
                                        choice.message_size,
                                        config.source_flit_size);
                                } else {
                                    choice.flits = std::stoi(size_key);
                                    choice.message_size =
                                        std::max(1, choice.flits) *
                                        config.source_flit_size;
                                }
                                choice.weight = count;
                                phases[phase_index].push_back(choice);
                                phase_endpoint_packets_by_source[src] +=
                                    rate_scale *
                                    static_cast<double>(count);
                                has_phase_endpoint_counts = true;
                            }
                        } else {
                            const uint64_t count =
                                static_cast<uint64_t>(count_json.number());
                            if (count == 0) {
                                continue;
                            }
                            ProfileEndpointChoice choice;
                            choice.vnet = vnet;
                            choice.destination = dst;
                            choice.weight = count;
                            phases[phase_index].push_back(choice);
                            phase_endpoint_packets_by_source[src] +=
                                rate_scale * static_cast<double>(count);
                            has_phase_endpoint_counts = true;
                        }
                    }
                }
            }
            phase_index++;
        }
    }
    if (config.closed_loop) {
        config.response_probability = request_packets == 0 ? 0.0 :
            std::min(1.0, static_cast<double>(response_packets) /
                          static_cast<double>(request_packets));
    }
    if (config.phased && !phase_source_rates.empty()) {
        bool phase_source_totals_match = true;
        for (const auto& [_, source] : by_source) {
            uint64_t source_packets = 0;
            for (const auto& choice : source.endpoints) {
                source_packets += choice.weight;
            }
            if (source_packets == 0) {
                continue;
            }
            const double expected =
                rate_scale * static_cast<double>(source_packets);
            const auto& phase_packets_by_source =
                has_phase_endpoint_counts ? phase_endpoint_packets_by_source :
                                            phase_fraction_packets_by_source;
            const auto it = phase_packets_by_source.find(source.source);
            double phased = it == phase_packets_by_source.end() ?
                0.0 : it->second;
            const double tolerance = std::max(1.0, expected * 0.01);
            if (std::abs(phased - expected) > tolerance) {
                phase_source_totals_match = false;
                break;
            }
        }
        if (!phase_source_totals_match) {
            config.phased = false;
            config.phase_end_cycles.clear();
            phase_source_rates.clear();
            config.sim_cycles = unphased_sim_cycles;
        }
    }
    for (auto& [_, source] : by_source) {
        uint64_t source_packets = 0;
        for (const auto& choice : source.endpoints) {
            source_packets += choice.weight;
        }
        if (source_packets == 0) {
            continue;
        }
        source.rate_per_cycle =
            rate_scale * static_cast<double>(source_packets) /
            static_cast<double>(config.sim_cycles);
        if (config.bursty) {
            auto it = source_burst_cv.find(source.source);
            source.burst_cv = it == source_burst_cv.end() ?
                phase_burst_cv : it->second;
        }
        if (config.phased && !phase_source_rates.empty()) {
            source.phase_rates_per_cycle.assign(
                phase_source_rates.size(), 0.0);
            const auto phase_endpoints_it =
                phase_endpoints_by_source.find(source.source);
            if (phase_endpoints_it != phase_endpoints_by_source.end()) {
                source.phase_endpoints_per_phase =
                    phase_endpoints_it->second;
                for (size_t i = 0;
                     i < source.phase_endpoints_per_phase.size() &&
                         i < phase_cycles_by_index.size();
                     i++) {
                    uint64_t phase_source_packets = 0;
                    for (const auto& choice :
                         source.phase_endpoints_per_phase[i]) {
                        phase_source_packets += choice.weight;
                    }
                    source.phase_rates_per_cycle[i] =
                        rate_scale *
                        static_cast<double>(phase_source_packets) /
                        static_cast<double>(phase_cycles_by_index[i]);
                }
            } else {
                for (size_t i = 0; i < phase_source_rates.size(); i++) {
                    auto it = phase_source_rates[i].find(source.source);
                    if (it != phase_source_rates[i].end()) {
                        source.phase_rates_per_cycle[i] = it->second;
                    }
                }
            }
        }
        if (config.flow_timing) {
            auto appendFlows =
                [&](const std::vector<ProfileEndpointChoice>& endpoints,
                    uint64_t schedule_start, uint64_t schedule_cycles) {
                    if (endpoints.empty() || schedule_cycles == 0) {
                        return;
                    }
                    std::map<uint64_t, ProfileFlowTraffic> flows_by_key;
                    for (const auto& choice : endpoints) {
                        auto& flow = flows_by_key[flowKey(
                            source.source, choice.vnet, choice.flits)];
                        flow.vnet = choice.vnet;
                        flow.flits = choice.flits;
                        flow.schedule_start_cycle = schedule_start;
                        flow.schedule_cycles = schedule_cycles;
                        flow.endpoints.push_back(choice);
                    }
                    for (auto& [key, flow] : flows_by_key) {
                        uint64_t flow_packets = 0;
                        for (const auto& choice : flow.endpoints) {
                            flow_packets += choice.weight;
                        }
                        if (flow_packets == 0) {
                            continue;
                        }
                        flow.rate_per_cycle =
                            rate_scale * static_cast<double>(flow_packets) /
                            static_cast<double>(schedule_cycles);
                        flow.packets_remaining = flow_packets;
                        auto it = flow_interarrival_cv.find(key);
                        flow.interarrival_cv =
                            it == flow_interarrival_cv.end() ?
                            1.0 : std::max(0.05, std::sqrt(it->second));
                        source.flows.push_back(std::move(flow));
                    }
                };
            if (config.phased &&
                !source.phase_endpoints_per_phase.empty() &&
                !phase_cycles_by_index.empty()) {
                uint64_t phase_start = 0;
                for (size_t i = 0;
                     i < source.phase_endpoints_per_phase.size() &&
                         i < phase_cycles_by_index.size();
                     i++) {
                    const uint64_t phase_cycles = phase_cycles_by_index[i];
                    appendFlows(
                        source.phase_endpoints_per_phase[i],
                        phase_start, phase_cycles);
                    phase_start += phase_cycles;
                }
            } else {
                appendFlows(source.endpoints, 0, config.sim_cycles);
            }
        }
        config.sources.push_back(std::move(source));
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

ProfileTraffic::ProfileTraffic(RuntimeNetwork& runtime,
                               ProfileTrafficConfig config)
    : _runtime(runtime), _config(std::move(config)),
      _rng(static_cast<uint32_t>(_config.seed))
{
    if (_config.flow_timing_auto) {
        const int latency_envelope = std::max(
            _runtime.max_link_latency, _runtime.max_router_latency);
        // Dense profiles already superpose many active flows; replaying each
        // flow's sampled CV can add artificial burst correlation.
        const bool sparse_profile =
            _config.profile_lambda_per_cpu <= 0.0 ||
            _config.profile_lambda_per_cpu < 0.002;
        _config.flow_timing = latency_envelope >= 8 && sparse_profile;
    }
    _stats.injected_by_vnet.assign(runtime.virtual_networks, 0);
    _stats.delivered_by_vnet.assign(runtime.virtual_networks, 0);
    _stats.injected_flits_by_vnet.assign(runtime.virtual_networks, 0);
    _stats.delivered_flits_by_vnet.assign(runtime.virtual_networks, 0);
    _outstanding_by_source.assign(runtime.nodes, 0);
    if (_config.flow_timing) {
        const uint64_t sim_cycles = std::max<uint64_t>(1, _config.sim_cycles);
        for (auto& source : _config.sources) {
            for (auto& flow : source.flows) {
                if (flow.packets_remaining == 0) {
                    continue;
                }
                const uint64_t schedule_start =
                    std::min(flow.schedule_start_cycle, sim_cycles - 1);
                const uint64_t schedule_end = std::min<uint64_t>(
                    sim_cycles,
                    schedule_start +
                        std::max<uint64_t>(1, flow.schedule_cycles));
                const uint64_t schedule_cycles =
                    std::max<uint64_t>(1, schedule_end - schedule_start);
                flow.scheduled_cycles.reserve(flow.packets_remaining);
                const double cv = std::max(0.05, flow.interarrival_cv);
                const double variance = cv * cv;
                const double shape = 1.0 / variance;
                const double scale = variance;
                std::gamma_distribution<double> gap(shape, scale);
                std::vector<double> gaps(flow.packets_remaining + 1);
                double total_gap = 0.0;
                for (auto& value : gaps) {
                    value = std::max(1.0e-9, gap(_rng));
                    total_gap += value;
                }
                double elapsed = gaps.front();
                for (uint64_t i = 0; i < flow.packets_remaining; i++) {
                    const double position =
                        total_gap > 0.0 ? elapsed / total_gap : 0.0;
                    const uint64_t cycle = std::min<uint64_t>(
                        schedule_end - 1,
                        schedule_start + static_cast<uint64_t>(
                            std::floor(position *
                                       static_cast<double>(schedule_cycles))));
                    flow.scheduled_cycles.push_back(cycle);
                    elapsed += gaps[i + 1];
                }
            }
        }
    }
    if (_config.bursty) {
        const uint64_t windows = std::max<uint64_t>(
            1, (_config.sim_cycles + _config.burst_window_cycles - 1) /
               _config.burst_window_cycles);
        for (auto& source : _config.sources) {
            source.burst_multipliers.assign(windows, 1.0);
            if (source.burst_cv <= 0.0) {
                continue;
            }
            const double variance = source.burst_cv * source.burst_cv;
            const double shape = 1.0 / variance;
            const double scale = variance;
            std::gamma_distribution<double> multiplier(shape, scale);
            double weighted_sum = 0.0;
            for (size_t i = 0; i < source.burst_multipliers.size(); i++) {
                auto& value = source.burst_multipliers[i];
                value = multiplier(_rng);
                const uint64_t window_start =
                    static_cast<uint64_t>(i) * _config.burst_window_cycles;
                const uint64_t window_end = std::min<uint64_t>(
                    _config.sim_cycles,
                    window_start + _config.burst_window_cycles);
                const uint64_t window_cycles =
                    window_end > window_start ? window_end - window_start : 0;
                weighted_sum += value * static_cast<double>(window_cycles);
            }
            if (weighted_sum <= 0.0) {
                std::fill(source.burst_multipliers.begin(),
                          source.burst_multipliers.end(), 1.0);
                continue;
            }
            const double norm = static_cast<double>(_config.sim_cycles) /
                weighted_sum;
            for (auto& value : source.burst_multipliers) {
                value *= norm;
            }
        }
        auto appendBurstySchedule =
            [&](ProfileSourceTraffic& source, uint64_t schedule_start,
                uint64_t schedule_cycles, double rate_per_cycle,
                uint64_t exact_packets) {
                if (schedule_cycles == 0 ||
                    (rate_per_cycle <= 0.0 && exact_packets == 0)) {
                    return;
                }
                const uint64_t schedule_end = std::min<uint64_t>(
                    _config.sim_cycles, schedule_start + schedule_cycles);
                if (schedule_end <= schedule_start) {
                    return;
                }
                const uint64_t packets = exact_packets > 0 ? exact_packets :
                    static_cast<uint64_t>(
                    std::llround(rate_per_cycle *
                                 static_cast<double>(
                                     schedule_end - schedule_start)));
                if (packets == 0) {
                    return;
                }

                struct Segment
                {
                    uint64_t start = 0;
                    uint64_t cycles = 0;
                    double weight = 0.0;
                    double cumulative = 0.0;
                };
                std::vector<Segment> segments;
                double total_weight = 0.0;
                uint64_t cursor = schedule_start;
                while (cursor < schedule_end) {
                    const size_t window_index = static_cast<size_t>(
                        cursor / _config.burst_window_cycles);
                    const uint64_t window_end = std::min<uint64_t>(
                        schedule_end,
                        (static_cast<uint64_t>(window_index) + 1) *
                            _config.burst_window_cycles);
                    const uint64_t cycles = window_end - cursor;
                    const double multiplier =
                        window_index < source.burst_multipliers.size() ?
                        source.burst_multipliers[window_index] : 1.0;
                    const double weight =
                        std::max(0.0, multiplier) *
                        static_cast<double>(cycles);
                    if (cycles > 0 && weight > 0.0) {
                        total_weight += weight;
                        segments.push_back(
                            {cursor, cycles, weight, total_weight});
                    }
                    cursor = window_end;
                }
                if (segments.empty() || total_weight <= 0.0) {
                    return;
                }

                std::uniform_real_distribution<double> jitter(0.0, 1.0);
                source.scheduled_cycles.reserve(
                    source.scheduled_cycles.size() + packets);
                for (uint64_t i = 0; i < packets; i++) {
                    const double target =
                        (static_cast<double>(i) + jitter(_rng)) *
                        total_weight / static_cast<double>(packets);
                    auto it = std::lower_bound(
                        segments.begin(), segments.end(), target,
                        [](const Segment& segment, double value) {
                            return segment.cumulative < value;
                        });
                    if (it == segments.end()) {
                        it = std::prev(segments.end());
                    }
                    const double previous =
                        it == segments.begin() ? 0.0 :
                                                 std::prev(it)->cumulative;
                    const double within = std::clamp(
                        (target - previous) / it->weight, 0.0, 1.0);
                    const uint64_t offset = std::min<uint64_t>(
                        it->cycles - 1,
                        static_cast<uint64_t>(
                            std::floor(within *
                                       static_cast<double>(it->cycles))));
                    source.scheduled_cycles.push_back(it->start + offset);
                }
            };
        for (auto& source : _config.sources) {
            uint64_t source_packets = 0;
            for (const auto& choice : source.endpoints) {
                source_packets += choice.weight;
            }
            if (_config.phased && !source.phase_rates_per_cycle.empty() &&
                !_config.phase_end_cycles.empty()) {
                uint64_t phase_start = 0;
                for (size_t i = 0; i < source.phase_rates_per_cycle.size();
                     i++) {
                    const uint64_t phase_end =
                        i < _config.phase_end_cycles.size() ?
                        _config.phase_end_cycles[i] : _config.sim_cycles;
                    if (phase_end > phase_start) {
                        uint64_t phase_packets = 0;
                        if (i < source.phase_endpoints_per_phase.size()) {
                            for (const auto& choice :
                                 source.phase_endpoints_per_phase[i]) {
                                phase_packets += choice.weight;
                            }
                        }
                        appendBurstySchedule(
                            source, phase_start, phase_end - phase_start,
                            source.phase_rates_per_cycle[i], phase_packets);
                    }
                    phase_start = phase_end;
                }
            } else {
                appendBurstySchedule(
                    source, 0, _config.sim_cycles, source.rate_per_cycle,
                    source_packets);
            }
            if (source.scheduled_cycles.size() < source_packets) {
                appendBurstySchedule(
                    source, 0, _config.sim_cycles, source.rate_per_cycle,
                    source_packets - source.scheduled_cycles.size());
            }
            std::sort(source.scheduled_cycles.begin(),
                      source.scheduled_cycles.end());
            if (source.scheduled_cycles.size() > source_packets) {
                source.scheduled_cycles.resize(source_packets);
            }
            _stats.scheduled_profile_packets +=
                source.scheduled_cycles.size();
        }
    }
}

void
ProfileTraffic::step(uint64_t cycle)
{
    _stats.cycles = cycle + 1;
    while (_config.phased &&
           _phase_index < _config.phase_end_cycles.size() &&
           cycle >= _config.phase_end_cycles[_phase_index]) {
        _phase_index++;
    }
    for (auto& source : _config.sources) {
        if (_config.flow_timing) {
            for (auto& flow : source.flows) {
                while (flow.next_packet_index <
                           flow.scheduled_cycles.size() &&
                       flow.scheduled_cycles[flow.next_packet_index] <=
                           cycle) {
                    injectEndpoint(source.source, chooseFlowEndpoint(flow));
                    flow.next_packet_index++;
                }
            }
            continue;
        }
        if (_config.bursty) {
            const auto* endpoints = &source.endpoints;
            if (_config.phased &&
                _phase_index < source.phase_endpoints_per_phase.size() &&
                !source.phase_endpoints_per_phase[_phase_index].empty()) {
                endpoints = &source.phase_endpoints_per_phase[_phase_index];
            }
            while (source.next_packet_index <
                       source.scheduled_cycles.size() &&
                   source.scheduled_cycles[source.next_packet_index] <=
                       cycle) {
                injectFromEndpoints(source.source, *endpoints);
                source.next_packet_index++;
            }
            continue;
        }
        double source_rate = source.rate_per_cycle;
        if (_config.phased &&
            _phase_index < source.phase_rates_per_cycle.size()) {
            source_rate = source.phase_rates_per_cycle[_phase_index];
        }
        const auto* endpoints = &source.endpoints;
        if (_config.phased &&
            _phase_index < source.phase_endpoints_per_phase.size() &&
            !source.phase_endpoints_per_phase[_phase_index].empty()) {
            endpoints = &source.phase_endpoints_per_phase[_phase_index];
        }
        const double rate = source_rate;
        std::poisson_distribution<int> sends(rate);
        const int count = sends(_rng);
        for (int i = 0; i < count; i++) {
            injectFromEndpoints(source.source, *endpoints);
        }
    }
    collectDelivered(cycle);
}

void
ProfileTraffic::drain(uint64_t cycle)
{
    _stats.cycles = cycle + 1;
    collectDelivered(cycle);
}

const ProfileEndpointChoice&
ProfileTraffic::chooseEndpoint(const ProfileSourceTraffic& source)
{
    return weightedChoice(_rng, source.endpoints);
}

const ProfileEndpointChoice&
ProfileTraffic::chooseFlowEndpoint(const ProfileFlowTraffic& flow)
{
    return weightedChoice(_rng, flow.endpoints);
}

int
ProfileTraffic::chooseMessageSize(int vnet)
{
    if (vnet >= 0 && vnet < static_cast<int>(_config.flits_by_vnet.size()) &&
        !_config.flits_by_vnet[vnet].empty()) {
        const auto& choice = weightedChoice(_rng, _config.flits_by_vnet[vnet]);
        if (choice.message_size > 0) {
            return choice.message_size;
        }
        return std::max(1, choice.flits) * _config.source_flit_size;
    }
    return _config.source_flit_size;
}

void
ProfileTraffic::inject(const ProfileSourceTraffic& source)
{
    injectFromEndpoints(source.source, source.endpoints);
}

void
ProfileTraffic::injectFromEndpoints(
    int source, const std::vector<ProfileEndpointChoice>& endpoints)
{
    if (endpoints.empty()) {
        return;
    }
    const auto& endpoint = weightedChoice(_rng, endpoints);
    injectEndpoint(source, endpoint);
}

void
ProfileTraffic::injectEndpoint(int source, const ProfileEndpointChoice& endpoint)
{
    if (source < 0 || source >= _runtime.nodes ||
        endpoint.destination < 0 || endpoint.destination >= _runtime.nodes ||
        endpoint.vnet < 0 || endpoint.vnet >= _runtime.virtual_networks) {
        _stats.invalid_profile_packets++;
        return;
    }
    if (_config.closed_loop &&
        _outstanding_by_source[source] >= _config.outstanding_limit) {
        return;
    }
    const int flit_size = static_cast<int>(_runtime.network->getNiFlitSize());
    const int message_size = endpoint.message_size > 0 ?
        endpoint.message_size :
        (endpoint.flits > 0 ? endpoint.flits * _config.source_flit_size :
                              chooseMessageSize(endpoint.vnet));
    const int flits = ceilDiv(message_size, flit_size);

    gem5::ruby::NetDest dest;
    dest.add(endpoint.destination);
    auto msg = std::make_shared<gem5::ruby::Message>(
        dest, message_size, gem5::curTick());
    if (_config.closed_loop) {
        msg->setTrafficOrigin(source);
        msg->setTrafficRequestVnet(endpoint.vnet);
        std::bernoulli_distribution respond(_config.response_probability);
        msg->setGenerateTrafficResponse(respond(_rng));
    }
    if (traceEnabled()) {
        traceEvent("profile.inject", {
            {"source", traceValue(source)},
            {"destination", traceValue(endpoint.destination)},
            {"vnet", traceValue(endpoint.vnet)},
            {"message_size", traceValue(message_size)},
            {"flits", traceValue(flits)},
        });
    }
    _runtime.to_net[source][endpoint.vnet]->enqueue(
        msg, gem5::curTick(), 0, nullptr);
    _stats.attempted++;
    _stats.injected++;
    _stats.injected_by_vnet[endpoint.vnet]++;
    _stats.injected_flits += flits;
    _stats.injected_flits_by_vnet[endpoint.vnet] += flits;
    if (_config.closed_loop) {
        _outstanding_by_source[source]++;
    }
}

void
ProfileTraffic::injectResponse(int source, int destination, int origin)
{
    if (source < 0 || source >= _runtime.nodes ||
        destination < 0 || destination >= _runtime.nodes ||
        _config.response_vnet < 0 ||
        _config.response_vnet >= _runtime.virtual_networks) {
        return;
    }
    const int flit_size = static_cast<int>(_runtime.network->getNiFlitSize());
    const int message_size = chooseMessageSize(_config.response_vnet);
    const int flits = ceilDiv(message_size, flit_size);

    gem5::ruby::NetDest dest;
    dest.add(destination);
    auto msg = std::make_shared<gem5::ruby::Message>(
        dest, message_size, gem5::curTick());
    msg->setTrafficOrigin(origin);
    msg->setTrafficRequestVnet(_config.response_vnet);
    if (traceEnabled()) {
        traceEvent("profile.response", {
            {"source", traceValue(source)},
            {"destination", traceValue(destination)},
            {"origin", traceValue(origin)},
            {"vnet", traceValue(_config.response_vnet)},
            {"message_size", traceValue(message_size)},
            {"flits", traceValue(flits)},
        });
    }
    _runtime.to_net[source][_config.response_vnet]->enqueue(
        msg, gem5::curTick(), 0, nullptr);
    _stats.attempted++;
    _stats.injected++;
    _stats.injected_by_vnet[_config.response_vnet]++;
    _stats.injected_flits += flits;
    _stats.injected_flits_by_vnet[_config.response_vnet] += flits;
}

void
ProfileTraffic::collectDelivered(uint64_t cycle)
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
                const uint64_t network_latency = msg->hasNetworkLatency() ?
                    static_cast<uint64_t>(msg->getNetworkLatency()) :
                    latency;
                if (traceEnabled()) {
                    traceEvent("profile.deliver", {
                        {"node", traceValue(node)},
                        {"vnet", traceValue(vnet)},
                        {"message_size", traceValue(message_size)},
                        {"flits", traceValue(flits)},
                        {"latency", traceValue(latency)},
                        {"network_latency", traceValue(network_latency)},
                    });
                }
                buffer->dequeueMsg(now);
                _stats.delivered++;
                _stats.packet_latency_sum += latency;
                _stats.packet_latencies.push_back(latency);
                _stats.packet_latency_samples.push_back({
                    latency, vnet, flits});
                _stats.packet_network_latency_sum += network_latency;
                _stats.packet_network_latencies.push_back(network_latency);
                _stats.packet_network_latency_samples.push_back({
                    network_latency, vnet, flits});
                _stats.delivered_by_vnet[vnet]++;
                _stats.delivered_flits += flits;
                _stats.delivered_flits_by_vnet[vnet] += flits;
                if (_config.closed_loop) {
                    const int origin = msg->getTrafficOrigin();
                    if (vnet == _config.response_vnet) {
                        if (origin >= 0 &&
                            origin < static_cast<int>(
                                _outstanding_by_source.size()) &&
                            _outstanding_by_source[origin] > 0) {
                            _outstanding_by_source[origin]--;
                        }
                    } else if (msg->shouldGenerateTrafficResponse()) {
                        injectResponse(node, origin, origin);
                    } else if (origin >= 0 &&
                               origin < static_cast<int>(
                                   _outstanding_by_source.size()) &&
                               _outstanding_by_source[origin] > 0) {
                        _outstanding_by_source[origin]--;
                    }
                }
            }
        }
    }
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
                const uint64_t network_latency = msg->hasNetworkLatency() ?
                    static_cast<uint64_t>(msg->getNetworkLatency()) :
                    latency;
                if (traceEnabled()) {
                    traceEvent("replay.deliver", {
                        {"node", traceValue(node)},
                        {"vnet", traceValue(vnet)},
                        {"message_size", traceValue(message_size)},
                        {"flits", traceValue(flits)},
                        {"latency", traceValue(latency)},
                        {"network_latency", traceValue(network_latency)},
                    });
                }
                buffer->dequeueMsg(now);
                _stats.delivered++;
                _stats.packet_latency_sum += latency;
                _stats.packet_latencies.push_back(latency);
                _stats.packet_latency_samples.push_back({
                    latency, vnet, flits});
                _stats.packet_network_latency_sum += network_latency;
                _stats.packet_network_latencies.push_back(network_latency);
                _stats.packet_network_latency_samples.push_back({
                    network_latency, vnet, flits});
                _stats.delivered_by_vnet[vnet]++;
                _stats.delivered_flits += flits;
                _stats.delivered_flits_by_vnet[vnet] += flits;
            }
        }
    }
}

} // namespace pace
