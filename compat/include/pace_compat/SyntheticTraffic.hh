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

struct SyntheticTrafficStats
{
    uint64_t attempted = 0;
    uint64_t injected = 0;
    uint64_t delivered = 0;
    uint64_t injected_flits = 0;
    uint64_t delivered_flits = 0;
    uint64_t cycles = 0;
    uint64_t packet_latency_sum = 0;
    std::vector<uint64_t> packet_latencies;
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

} // namespace pace

#endif // __PACE_COMPAT_SYNTHETIC_TRAFFIC_HH__
