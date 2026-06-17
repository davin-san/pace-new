#ifndef __PACE_COMPAT_SYNTHETIC_TRAFFIC_HH__
#define __PACE_COMPAT_SYNTHETIC_TRAFFIC_HH__

#include <cstdint>
#include <random>
#include <string>
#include <vector>

#include "pace_compat/RuntimeNetwork.hh"

namespace pace
{

struct SyntheticTrafficConfig
{
    uint64_t sim_cycles = 1000;
    uint64_t drain_cycles = 200;
    std::string synthetic = "uniform_random";
    double injectionrate = 0.01;
    int inj_vnet = -1;
    int single_sender_id = -1;
    int single_dest_id = -1;
    int num_packets_max = -1;
    int seed = 1;
    int precision = 3;
};

struct TrafficLatencySample
{
    uint64_t latency = 0;
    int vnet = 0;
    int flits = 0;
};

struct SyntheticTrafficStats
{
    uint64_t attempted = 0;
    uint64_t injected = 0;
    uint64_t delivered = 0;
    uint64_t injected_flits = 0;
    uint64_t delivered_flits = 0;
    uint64_t cycles = 0;
    uint64_t scheduled_profile_packets = 0;
    uint64_t invalid_profile_packets = 0;
    uint64_t packet_latency_sum = 0;
    uint64_t packet_network_latency_sum = 0;
    std::vector<uint64_t> packet_latencies;
    std::vector<uint64_t> packet_network_latencies;
    std::vector<TrafficLatencySample> packet_latency_samples;
    std::vector<TrafficLatencySample> packet_network_latency_samples;
    std::vector<uint64_t> injected_by_vnet;
    std::vector<uint64_t> delivered_by_vnet;
    std::vector<uint64_t> injected_flits_by_vnet;
    std::vector<uint64_t> delivered_flits_by_vnet;
};

struct ReplayPacket
{
    uint64_t cycle = 0;
    int source = 0;
    int destination = 0;
    int vnet = 0;
    int message_size = 0;
    int flits = 0;
};

struct ReplayTrafficConfig
{
    uint64_t sim_cycles = 0;
    uint64_t drain_cycles = 200;
    std::vector<ReplayPacket> packets;
};

struct ProfileEndpointChoice
{
    int vnet = 0;
    int destination = 0;
    int message_size = 0;
    int flits = 0;
    uint64_t weight = 0;
};

struct ProfileFlitChoice
{
    int message_size = 0;
    int flits = 1;
    uint64_t weight = 0;
};

struct ProfileFlowTraffic
{
    int vnet = 0;
    int flits = 0;
    uint64_t schedule_start_cycle = 0;
    uint64_t schedule_cycles = 0;
    double rate_per_cycle = 0.0;
    double interarrival_cv = 1.0;
    double next_cycle = 0.0;
    uint64_t packets_remaining = 0;
    size_t next_packet_index = 0;
    std::vector<uint64_t> scheduled_cycles;
    std::vector<ProfileEndpointChoice> endpoints;
};

struct ProfileSourceTraffic
{
    int source = 0;
    double rate_per_cycle = 0.0;
    std::vector<double> phase_rates_per_cycle;
    std::vector<std::vector<ProfileEndpointChoice>> phase_endpoints_per_phase;
    double burst_cv = 0.0;
    double burst_multiplier = 1.0;
    uint64_t next_burst_cycle = 0;
    size_t burst_index = 0;
    size_t next_packet_index = 0;
    std::vector<double> burst_multipliers;
    std::vector<uint64_t> scheduled_cycles;
    std::vector<ProfileEndpointChoice> endpoints;
    std::vector<ProfileFlowTraffic> flows;
};

struct ProfileTrafficConfig
{
    uint64_t sim_cycles = 0;
    uint64_t drain_cycles = 200;
    int seed = 1;
    bool closed_loop = false;
    bool bursty = false;
    bool phased = false;
    bool flow_timing = false;
    bool flow_timing_auto = false;
    int response_vnet = 1;
    int outstanding_limit = 16;
    int source_flit_size = 16;
    uint64_t burst_window_cycles = 0;
    double response_probability = 1.0;
    double profile_lambda_per_cpu = 0.0;
    std::vector<uint64_t> phase_end_cycles;
    std::vector<ProfileSourceTraffic> sources;
    std::vector<std::vector<ProfileFlitChoice>> flits_by_vnet;
};

class SyntheticTraffic
{
  public:
    SyntheticTraffic(RuntimeNetwork& runtime, SyntheticTrafficConfig config);

    void step(uint64_t cycle);
    void drain(uint64_t cycle);
    SyntheticTrafficStats stats() const { return _stats; }

  private:
    enum class TrafficType {
        bit_complement,
        bit_reverse,
        bit_rotation,
        neighbor,
        shuffle,
        tornado,
        transpose,
        uniform_random,
    };

    void injectForSource(int source);
    void injectMessage(int source, int destination, int vnet);
    void collectDelivered(uint64_t cycle);
    int chooseDestination(int source);
    int chooseVnet();
    TrafficType parseTraffic(const std::string& name) const;
    int messageSizeForVnet(int vnet) const;
    int flitsForMessage(int vnet) const;

    RuntimeNetwork& _runtime;
    SyntheticTrafficConfig _config;
    TrafficType _traffic;
    std::vector<int> _sent_by_source;
    std::mt19937 _rng;
    SyntheticTrafficStats _stats;
};

class ReplayTraffic
{
  public:
    ReplayTraffic(RuntimeNetwork& runtime, ReplayTrafficConfig config);

    void step(uint64_t cycle);
    void drain(uint64_t cycle);
    SyntheticTrafficStats stats() const { return _stats; }

  private:
    void inject(const ReplayPacket& packet);
    void collectDelivered(uint64_t cycle);

    RuntimeNetwork& _runtime;
    ReplayTrafficConfig _config;
    size_t _next_packet = 0;
    SyntheticTrafficStats _stats;
};

ReplayTrafficConfig loadReplayTrafficConfig(
    const std::string& replay_json, uint64_t drain_override);

class ProfileTraffic
{
  public:
    ProfileTraffic(RuntimeNetwork& runtime, ProfileTrafficConfig config);

    void step(uint64_t cycle);
    void drain(uint64_t cycle);
    SyntheticTrafficStats stats() const { return _stats; }

  private:
    void inject(const ProfileSourceTraffic& source);
    void injectFromEndpoints(
        int source, const std::vector<ProfileEndpointChoice>& endpoints);
    void injectEndpoint(int source, const ProfileEndpointChoice& endpoint);
    void injectResponse(int source, int destination, int origin);
    void collectDelivered(uint64_t cycle);
    const ProfileEndpointChoice& chooseEndpoint(
        const ProfileSourceTraffic& source);
    const ProfileEndpointChoice& chooseFlowEndpoint(
        const ProfileFlowTraffic& flow);
    int chooseMessageSize(int vnet);

    RuntimeNetwork& _runtime;
    ProfileTrafficConfig _config;
    std::mt19937 _rng;
    SyntheticTrafficStats _stats;
    std::vector<int> _outstanding_by_source;
    size_t _phase_index = 0;
};

ProfileTrafficConfig loadProfileTrafficConfig(
    const std::string& profile_json, uint64_t sim_cycles_override,
    uint64_t drain_override, double rate_scale, bool closed_loop,
    bool bursty, bool phased, bool flow_timing, bool flow_timing_auto);

} // namespace pace

#endif // __PACE_COMPAT_SYNTHETIC_TRAFFIC_HH__
