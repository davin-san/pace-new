#include <exception>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <map>
#include <string>
#include <vector>

#include "pace_compat/EventQueue.hh"
#include "pace_compat/Json.hh"
#include "pace_compat/RuntimeNetwork.hh"
#include "pace_compat/SyntheticTraffic.hh"
#include "pace_compat/Trace.hh"

namespace
{

void
usage(const char* program)
{
    std::cerr << "Usage: " << program << " --topology-json <path> [--simulate]"
              << " [--drain-cycles N] [--stats-json path]"
              << " [--trace-jsonl path] [--replay-json path]"
              << " [--traffic-profile-json path] [--profile-sim-cycles N]"
              << " [--profile-rate-scale X] [--profile-closed-loop]"
              << " [--profile-bursty] [--profile-phased]"
              << " [--profile-flow-timing]"
              << " [--profile-flow-timing-auto]\n";
}

int
jsonInt(const pace::Json& obj, const std::string& key, int fallback)
{
    return obj.contains(key) ? static_cast<int>(obj.at(key).number()) :
                               fallback;
}

uint64_t
jsonU64(const pace::Json& obj, const std::string& key, uint64_t fallback)
{
    return obj.contains(key) ? static_cast<uint64_t>(obj.at(key).number()) :
                               fallback;
}

double
jsonDouble(const pace::Json& obj, const std::string& key, double fallback)
{
    return obj.contains(key) ? obj.at(key).number() : fallback;
}

std::string
jsonString(const pace::Json& obj, const std::string& key,
           const std::string& fallback)
{
    return obj.contains(key) ? obj.at(key).string() : fallback;
}

pace::SyntheticTrafficConfig
loadTrafficConfig(const std::string& topology_json, uint64_t drain_override)
{
    pace::SyntheticTrafficConfig config;
    pace::Json root = pace::parseJsonFile(topology_json);
    if (!root.contains("simulation")) {
        if (drain_override > 0) {
            config.drain_cycles = drain_override;
        }
        return config;
    }

    const pace::Json& sim = root.at("simulation");
    config.sim_cycles = jsonU64(sim, "sim_cycles", config.sim_cycles);
    config.synthetic = jsonString(sim, "synthetic", config.synthetic);
    config.injectionrate =
        jsonDouble(sim, "injectionrate", config.injectionrate);
    config.inj_vnet = jsonInt(sim, "inj_vnet", config.inj_vnet);
    config.single_sender_id =
        jsonInt(sim, "single_sender_id", config.single_sender_id);
    config.single_dest_id =
        jsonInt(sim, "single_dest_id", config.single_dest_id);
    config.num_packets_max =
        jsonInt(sim, "num_packets_max", config.num_packets_max);
    config.seed = jsonInt(sim, "seed", config.seed);
    if (drain_override > 0) {
        config.drain_cycles = drain_override;
    }
    return config;
}

void
writeMap(std::ostream& out, const std::vector<uint64_t>& values,
         int indent)
{
    out << "{";
    bool first = true;
    for (size_t key = 0; key < values.size(); key++) {
        const uint64_t value = values[key];
        if (value == 0) {
            continue;
        }
        if (!first) {
            out << ",";
        }
        out << "\n" << std::string(indent + 2, ' ') << "\"" << key
            << "\": " << value;
        first = false;
    }
    if (!values.empty()) {
        out << "\n" << std::string(indent, ' ');
    }
    out << "}";
}

uint64_t percentileNearestRank(std::vector<uint64_t> values, int percentile);

void
writePacketLatencyBreakdown(
    std::ostream& out,
    const std::vector<pace::TrafficLatencySample>& samples,
    int indent)
{
    std::map<int, std::map<int, std::vector<uint64_t>>> grouped;
    for (const auto& sample : samples) {
        grouped[sample.vnet][sample.flits].push_back(sample.latency);
    }
    out << "{";
    bool first_vnet = true;
    for (auto& [vnet, by_flits] : grouped) {
        if (!first_vnet) {
            out << ",";
        }
        out << "\n" << std::string(indent + 2, ' ') << "\"" << vnet
            << "\": {";
        bool first_flits = true;
        for (auto& [flits, values] : by_flits) {
            uint64_t sum = 0;
            for (const uint64_t value : values) {
                sum += value;
            }
            const double avg = values.empty() ? 0.0 :
                static_cast<double>(sum) / static_cast<double>(values.size());
            const uint64_t p99 = percentileNearestRank(values, 99);
            if (!first_flits) {
                out << ",";
            }
            out << "\n" << std::string(indent + 4, ' ') << "\"" << flits
                << "\": {\"count\": " << values.size()
                << ", \"avg\": " << avg
                << ", \"p99\": " << p99 << "}";
            first_flits = false;
        }
        if (!by_flits.empty()) {
            out << "\n" << std::string(indent + 2, ' ');
        }
        out << "}";
        first_vnet = false;
    }
    if (!grouped.empty()) {
        out << "\n" << std::string(indent, ' ');
    }
    out << "}";
}

const char*
linkTypeName(gem5::ruby::garnet::link_type type)
{
    using namespace gem5::ruby::garnet;
    switch (type) {
      case EXT_IN_: return "ext_in";
      case EXT_OUT_: return "ext_out";
      case INT_: return "int";
      default: return "unknown";
    }
}

uint64_t
percentileNearestRank(std::vector<uint64_t> values, int percentile)
{
    if (values.empty()) {
        return 0;
    }
    std::sort(values.begin(), values.end());
    const size_t rank =
        (static_cast<size_t>(percentile) * values.size() + 99) / 100;
    const size_t index = std::min(rank == 0 ? size_t{0} : rank - 1,
                                  values.size() - 1);
    return values[index];
}

void
writeStatsJson(const std::string& path, const pace::RuntimeNetwork& runtime,
               const pace::SyntheticTrafficStats& stats)
{
    uint64_t total_link_utilization = 0;
    std::map<std::string, uint64_t> link_utilization_by_type;
    for (const auto& link : runtime.network_links) {
        const uint64_t utilization = link->getLinkUtilization();
        total_link_utilization += utilization;
        link_utilization_by_type[linkTypeName(link->getType())] += utilization;
    }

    std::ofstream out(path);
    if (!out.is_open()) {
        throw std::runtime_error("could not open stats json: " + path);
    }
    const double avg_packet_latency = stats.delivered == 0 ? 0.0 :
        static_cast<double>(stats.packet_latency_sum) /
        static_cast<double>(stats.delivered);
    const uint64_t p99_packet_latency =
        percentileNearestRank(stats.packet_latencies, 99);
    const double avg_packet_network_latency =
        stats.delivered == 0 ? 0.0 :
        static_cast<double>(stats.packet_network_latency_sum) /
        static_cast<double>(stats.delivered);
    const uint64_t p99_packet_network_latency =
        percentileNearestRank(stats.packet_network_latencies, 99);
    out << "{\n";
    out << "  \"schema\": \"pace.garnet.stats.v1\",\n";
    out << "  \"cycles\": " << stats.cycles << ",\n";
    out << "  \"traffic\": {\n";
    out << "    \"attempted_packets\": " << stats.attempted << ",\n";
    out << "    \"injected_packets\": " << stats.injected << ",\n";
    out << "    \"delivered_packets\": " << stats.delivered << ",\n";
    out << "    \"scheduled_profile_packets\": "
        << stats.scheduled_profile_packets << ",\n";
    out << "    \"invalid_profile_packets\": "
        << stats.invalid_profile_packets << ",\n";
    out << "    \"injected_flits\": " << stats.injected_flits << ",\n";
    out << "    \"delivered_flits\": " << stats.delivered_flits << ",\n";
    out << "    \"avg_packet_latency_cycles\": " << avg_packet_latency << ",\n";
    out << "    \"p99_packet_latency_cycles\": " << p99_packet_latency << ",\n";
    out << "    \"avg_packet_network_latency_cycles\": "
        << avg_packet_network_latency << ",\n";
    out << "    \"p99_packet_network_latency_cycles\": "
        << p99_packet_network_latency << ",\n";
    out << "    \"packet_latency_by_vnet_flits\": ";
    writePacketLatencyBreakdown(out, stats.packet_latency_samples, 4);
    out << ",\n";
    out << "    \"packet_network_latency_by_vnet_flits\": ";
    writePacketLatencyBreakdown(out, stats.packet_network_latency_samples, 4);
    out << ",\n";
    out << "    \"injected_by_vnet\": ";
    writeMap(out, stats.injected_by_vnet, 4);
    out << ",\n";
    out << "    \"delivered_by_vnet\": ";
    writeMap(out, stats.delivered_by_vnet, 4);
    out << ",\n";
    out << "    \"injected_flits_by_vnet\": ";
    writeMap(out, stats.injected_flits_by_vnet, 4);
    out << ",\n";
    out << "    \"delivered_flits_by_vnet\": ";
    writeMap(out, stats.delivered_flits_by_vnet, 4);
    out << "\n  },\n";
    out << "  \"garnet\": {\n";
    out << "    \"network_links\": " << runtime.network_links.size() << ",\n";
    out << "    \"credit_links\": " << runtime.credit_links.size() << ",\n";
    out << "    \"total_link_utilization\": " << total_link_utilization
        << ",\n";
    out << "    \"link_utilization_by_type\": {";
    bool first = true;
    for (const auto& [type, value] : link_utilization_by_type) {
        if (!first) {
            out << ",";
        }
        out << "\n      \"" << type << "\": " << value;
        first = false;
    }
    if (!link_utilization_by_type.empty()) {
        out << "\n    ";
    }
    out << "}\n";
    out << "  }\n";
    out << "}\n";
}

} // namespace

int
main(int argc, char** argv)
{
    std::string topology_json;
    std::string stats_json;
    std::string trace_jsonl;
    std::string replay_json;
    std::string traffic_profile_json;
    bool simulate = false;
    uint64_t drain_cycles = 0;
    uint64_t profile_sim_cycles = 0;
    double profile_rate_scale = 1.0;
    bool profile_closed_loop = false;
    bool profile_bursty = false;
    bool profile_phased = false;
    bool profile_flow_timing = false;
    bool profile_flow_timing_auto = false;
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--topology-json" && i + 1 < argc) {
            topology_json = argv[++i];
        } else if (arg == "--simulate") {
            simulate = true;
        } else if (arg == "--drain-cycles" && i + 1 < argc) {
            drain_cycles = std::stoull(argv[++i]);
        } else if (arg == "--stats-json" && i + 1 < argc) {
            stats_json = argv[++i];
        } else if (arg == "--trace-jsonl" && i + 1 < argc) {
            trace_jsonl = argv[++i];
        } else if (arg == "--replay-json" && i + 1 < argc) {
            replay_json = argv[++i];
            simulate = true;
        } else if (arg == "--traffic-profile-json" && i + 1 < argc) {
            traffic_profile_json = argv[++i];
            simulate = true;
        } else if (arg == "--profile-sim-cycles" && i + 1 < argc) {
            profile_sim_cycles = std::stoull(argv[++i]);
        } else if (arg == "--profile-rate-scale" && i + 1 < argc) {
            profile_rate_scale = std::stod(argv[++i]);
        } else if (arg == "--profile-closed-loop") {
            profile_closed_loop = true;
        } else if (arg == "--profile-bursty") {
            profile_bursty = true;
        } else if (arg == "--profile-phased") {
            profile_phased = true;
        } else if (arg == "--profile-flow-timing") {
            profile_flow_timing = true;
        } else if (arg == "--profile-flow-timing-auto") {
            profile_flow_timing = true;
            profile_flow_timing_auto = true;
        } else if (arg == "--help" || arg == "-h") {
            usage(argv[0]);
            return 0;
        } else {
            std::cerr << "Unknown argument: " << arg << "\n";
            usage(argv[0]);
            return 1;
        }
    }

    if (topology_json.empty()) {
        usage(argv[0]);
        return 1;
    }

    try {
        if (!trace_jsonl.empty()) {
            pace::setTraceFile(trace_jsonl);
            pace::traceEvent("simulation.trace_enabled", {
                {"path", pace::traceValue(trace_jsonl)},
            });
        }
        auto runtime = pace::instantiateRuntimeNetwork(topology_json);
        std::cout << "instantiated Garnet network"
                  << " nodes=" << runtime.nodes
                  << " routers=" << runtime.routers.size()
                  << " ext_links=" << runtime.ext_links.size()
                  << " int_links=" << runtime.int_links.size()
                  << " network_links=" << runtime.network_links.size()
                  << " credit_links=" << runtime.credit_links.size()
                  << " bridges=" << runtime.bridges.size()
                  << " vnets=" << runtime.virtual_networks << "\n";
        if (simulate) {
            pace::SyntheticTrafficStats stats;
            if (!traffic_profile_json.empty()) {
                auto config = pace::loadProfileTrafficConfig(
                    traffic_profile_json, profile_sim_cycles, drain_cycles,
                    profile_rate_scale, profile_closed_loop, profile_bursty,
                    profile_phased, profile_flow_timing,
                    profile_flow_timing_auto);
                pace::ProfileTraffic traffic(runtime, config);
                for (uint64_t cycle = 0; cycle < config.sim_cycles; cycle++) {
                    gem5::eventQueue().setCurTick(cycle);
                    traffic.step(cycle);
                    gem5::eventQueue().process();
                    traffic.drain(cycle);
                }
                for (uint64_t i = 0; i < config.drain_cycles; i++) {
                    uint64_t cycle = config.sim_cycles + i;
                    gem5::eventQueue().setCurTick(cycle);
                    gem5::eventQueue().process();
                    traffic.drain(cycle);
                }
                stats = traffic.stats();
            } else if (!replay_json.empty()) {
                auto config = pace::loadReplayTrafficConfig(
                    replay_json, drain_cycles);
                pace::ReplayTraffic traffic(runtime, config);
                for (uint64_t cycle = 0; cycle < config.sim_cycles; cycle++) {
                    gem5::eventQueue().setCurTick(cycle);
                    traffic.step(cycle);
                    gem5::eventQueue().process();
                    traffic.drain(cycle);
                }
                for (uint64_t i = 0; i < config.drain_cycles; i++) {
                    uint64_t cycle = config.sim_cycles + i;
                    gem5::eventQueue().setCurTick(cycle);
                    gem5::eventQueue().process();
                    traffic.drain(cycle);
                }
                stats = traffic.stats();
            } else {
                auto config = loadTrafficConfig(topology_json, drain_cycles);
                pace::SyntheticTraffic traffic(runtime, config);
                for (uint64_t cycle = 0; cycle < config.sim_cycles; cycle++) {
                    gem5::eventQueue().setCurTick(cycle);
                    traffic.step(cycle);
                    gem5::eventQueue().process();
                    traffic.drain(cycle);
                }
                for (uint64_t i = 0; i < config.drain_cycles; i++) {
                    uint64_t cycle = config.sim_cycles + i;
                    gem5::eventQueue().setCurTick(cycle);
                    gem5::eventQueue().process();
                    traffic.drain(cycle);
                }
                stats = traffic.stats();
            }
            pace::traceEvent("simulation.complete", {
                {"cycles", pace::traceValue(stats.cycles)},
                {"attempted", pace::traceValue(stats.attempted)},
                {"injected", pace::traceValue(stats.injected)},
                {"delivered", pace::traceValue(stats.delivered)},
                {"injected_flits", pace::traceValue(stats.injected_flits)},
                {"delivered_flits", pace::traceValue(stats.delivered_flits)},
            });
            std::cout << "simulation complete"
                      << " cycles=" << stats.cycles
                      << " attempted=" << stats.attempted
                      << " injected=" << stats.injected
                      << " delivered=" << stats.delivered
                      << " injected_flits=" << stats.injected_flits
                      << " delivered_flits=" << stats.delivered_flits
                      << "\n";
            if (!stats_json.empty()) {
                writeStatsJson(stats_json, runtime, stats);
            }
        } else {
            pace::traceEvent("simulation.complete", {
                {"cycles", pace::traceValue(0)},
                {"attempted", pace::traceValue(0)},
                {"injected", pace::traceValue(0)},
                {"delivered", pace::traceValue(0)},
                {"injected_flits", pace::traceValue(0)},
                {"delivered_flits", pace::traceValue(0)},
            });
        }
        pace::closeTraceFile();
    } catch (const std::exception& e) {
        pace::closeTraceFile();
        std::cerr << "pace-new error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
