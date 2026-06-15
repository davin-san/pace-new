from pathlib import Path

root = Path("/storage/scratch1/9/daoyama3/pace_new_v25_mape_20260606/gem5_profiler_build/gem5")
hh = root / "src/mem/ruby/network/garnet/PaceProfiler.hh"
cc = root / "src/mem/ruby/network/garnet/PaceProfiler.cc"

text = hh.read_text()
if "phaseIndex(Tick tick)" not in text:
    text = text.replace(
        "    double computeMaxLatency() const;\n",
        "    size_t phaseIndex(Tick tick);\n"
        "    void ensurePhase(size_t phase);\n"
        "    double computeMaxLatency() const;\n",
    )
if "m_phase_ticks" not in text:
    text = text.replace(
        "    // ---- Packet network latency samples by vnet and packet flit count ----\n",
        "    // ---- Per-phase topology-independent component pair extraction ----\n"
        "    // Enabled by PACE_PROFILER_PHASE_TICKS. Phase 0 starts at the first\n"
        "    // profiled injection tick so that counts follow the ROI extraction window.\n"
        "    Tick m_phase_ticks;\n"
        "    Tick m_phase_origin_tick;\n"
        "    bool m_phase_enabled;\n"
        "    bool m_phase_origin_valid;\n"
        "    std::vector<std::vector<std::vector<\n"
        "        std::unordered_map<int, std::unordered_map<int, uint64_t>>>>>\n"
        "        m_phase_src_dst_ni_flits_inject_by_vnet;\n\n"
        "    // ---- Packet network latency samples by vnet and packet flit count ----\n",
    )
hh.write_text(text)

text = cc.read_text()
if '#include <cstdlib>' not in text:
    text = text.replace('#include <algorithm>\n', '#include <algorithm>\n#include <cstdlib>\n')

old = """      m_src_dst_ni_flits_inject_by_vnet(3,
          std::vector<std::unordered_map<int,
              std::unordered_map<int, uint64_t>>>(max_nodes)),
      m_packet_latency_by_vnet_flits(3)
{"""
new = """      m_src_dst_ni_flits_inject_by_vnet(3,
          std::vector<std::unordered_map<int,
              std::unordered_map<int, uint64_t>>>(max_nodes)),
      m_phase_ticks(0),
      m_phase_origin_tick(0),
      m_phase_enabled(false),
      m_phase_origin_valid(false),
      m_packet_latency_by_vnet_flits(3)
{"""
if old in text:
    text = text.replace(old, new)

old = """    std::memset(m_fine,       0, sizeof(m_fine));
    std::memset(m_coarse,     0, sizeof(m_coarse));
    std::memset(m_ultra,      0, sizeof(m_ultra));
    std::memset(m_vnet_pkts,  0, sizeof(m_vnet_pkts));
    std::memset(m_vnet_flits, 0, sizeof(m_vnet_flits));
}"""
new = """    std::memset(m_fine,       0, sizeof(m_fine));
    std::memset(m_coarse,     0, sizeof(m_coarse));
    std::memset(m_ultra,      0, sizeof(m_ultra));
    std::memset(m_vnet_pkts,  0, sizeof(m_vnet_pkts));
    std::memset(m_vnet_flits, 0, sizeof(m_vnet_flits));

    const char* phase_ticks_env = std::getenv("PACE_PROFILER_PHASE_TICKS");
    if (phase_ticks_env != nullptr) {
        const unsigned long long phase_ticks = std::strtoull(
            phase_ticks_env, nullptr, 10);
        if (phase_ticks > 0) {
            m_phase_ticks = static_cast<Tick>(phase_ticks);
            m_phase_enabled = true;
        }
    }
}

size_t
PaceProfiler::phaseIndex(Tick tick)
{
    if (!m_phase_origin_valid) {
        m_phase_origin_tick = tick;
        m_phase_origin_valid = true;
    }
    if (m_phase_ticks == 0 || tick <= m_phase_origin_tick) {
        return 0;
    }
    return static_cast<size_t>((tick - m_phase_origin_tick) / m_phase_ticks);
}

void
PaceProfiler::ensurePhase(size_t phase)
{
    while (m_phase_src_dst_ni_flits_inject_by_vnet.size() <= phase) {
        m_phase_src_dst_ni_flits_inject_by_vnet.emplace_back(
            3, std::vector<std::unordered_map<int,
                std::unordered_map<int, uint64_t>>>(m_max_nodes));
    }
}"""
if old in text and "PACE_PROFILER_PHASE_TICKS" not in text:
    text = text.replace(old, new)

old = """        if (ni_id >= 0 && ni_id < m_max_nodes && dest_ni >= 0) {
            m_src_dst_ni_inject_by_vnet[vnet][ni_id][dest_ni]++;
            if (num_flits > 0) {
                m_src_dst_ni_flits_inject_by_vnet[vnet][ni_id]
                    [dest_ni][num_flits]++;
            }
        }
    }"""
new = """        if (ni_id >= 0 && ni_id < m_max_nodes && dest_ni >= 0) {
            m_src_dst_ni_inject_by_vnet[vnet][ni_id][dest_ni]++;
            if (num_flits > 0) {
                m_src_dst_ni_flits_inject_by_vnet[vnet][ni_id]
                    [dest_ni][num_flits]++;
            }
        }
        if (m_phase_enabled && ni_id >= 0 && ni_id < m_max_nodes &&
            dest_ni >= 0 && num_flits > 0) {
            const size_t phase = phaseIndex(tick);
            ensurePhase(phase);
            m_phase_src_dst_ni_flits_inject_by_vnet[phase][vnet][ni_id]
                [dest_ni][num_flits]++;
        }
    }"""
if old in text and "m_phase_src_dst_ni_flits_inject_by_vnet[phase]" not in text:
    text = text.replace(old, new)

old = r"""    out << "}\n";
    out << "}\n";

    out.close();"""
new = r"""    out << "},\n";

    // ---- Exact per-phase topology-independent source-destination NI counts,
    //      split by packet flit count ----
    out << "  \"phase_src_dst_ni_flits_counts_by_vnet\": [";
    bool first_phase = true;
    for (size_t phase = 0;
         phase < m_phase_src_dst_ni_flits_inject_by_vnet.size();
         ++phase) {
        bool phase_has_rows = false;
        for (int v = 0; v < 3 && !phase_has_rows; ++v) {
            for (int i = 0; i < m_max_nodes; ++i) {
                if (!m_phase_src_dst_ni_flits_inject_by_vnet[phase][v][i].empty()) {
                    phase_has_rows = true;
                    break;
                }
            }
        }
        if (!phase_has_rows) continue;
        if (!first_phase) out << ", ";
        out << "{\"phase_index\": " << phase
            << ", \"src_dst_ni_flits_counts_by_vnet\": {";
        bool phase_first_vnet = true;
        for (int v = 0; v < 3; ++v) {
            bool has_rows = false;
            for (int i = 0; i < m_max_nodes; ++i) {
                if (!m_phase_src_dst_ni_flits_inject_by_vnet[phase][v][i].empty()) {
                    has_rows = true;
                    break;
                }
            }
            if (!has_rows) continue;
            if (!phase_first_vnet) out << ", ";
            out << "\"" << v << "\": {";
            bool first_src_by_vnet = true;
            for (int i = 0; i < m_max_nodes; ++i) {
                if (m_phase_src_dst_ni_flits_inject_by_vnet[phase][v][i].empty()) continue;
                if (!first_src_by_vnet) out << ", ";
                out << "\"" << i << "\": {";
                bool first_dst_by_vnet = true;
                for (const auto &dst_kv :
                     m_phase_src_dst_ni_flits_inject_by_vnet[phase][v][i]) {
                    if (!first_dst_by_vnet) out << ", ";
                    out << "\"" << dst_kv.first << "\": {";
                    bool first_flits_by_dst = true;
                    for (const auto &flits_kv : dst_kv.second) {
                        if (!first_flits_by_dst) out << ", ";
                        out << "\"" << flits_kv.first << "\": "
                            << flits_kv.second;
                        first_flits_by_dst = false;
                    }
                    out << "}";
                    first_dst_by_vnet = false;
                }
                out << "}";
                first_src_by_vnet = false;
            }
            out << "}";
            phase_first_vnet = false;
        }
        out << "}}";
        first_phase = false;
    }
    out << "]\n";
    out << "}\n";

    out.close();"""
if old in text and "phase_src_dst_ni_flits_counts_by_vnet" not in text:
    text = text.replace(old, new)
cc.write_text(text)

sim = Path("/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/scripts/pace_sim_v25_mesh_params.py")
text = sim.read_text()
text = text.replace('os.environ["PACE_PROFILER_PHASE_TICKS"] = str(phase_ticks)\n', "")
text = text.replace('os.environ["PACE_PROFILER_PHASE_TICKS"] = str(cli.phase_ticks)\n', "")
needle = "cli = parser.parse_args()\n"
insert = (
    "cli = parser.parse_args()\n"
    "# PaceProfiler is constructed during Ruby/Garnet instantiation, so this\n"
    "# environment variable must be set before any system objects are built.\n"
    "os.environ[\"PACE_PROFILER_PHASE_TICKS\"] = str(cli.phase_ticks)\n"
)
if "PACE_PROFILER_PHASE_TICKS" not in text:
    text = text.replace(needle, insert)
sim.write_text(text)

builder = Path("/storage/home/hcoda1/9/daoyama3/r-chao33-0/experiments/pace_new_v25_mape_20260606/scripts/build_component_traffic_profile.py")
text = builder.read_text()
old = """    for phase in phases:
        phase_ticks = int(phase.get("sim_ticks", 0) or 0)"""
new = """    exact_phase_counts = {
        int(row.get("phase_index", -1)): row.get(
            "src_dst_ni_flits_counts_by_vnet", {})
        for row in extra.get("phase_src_dst_ni_flits_counts_by_vnet", [])
    }
    for phase in phases:
        phase_ticks = int(phase.get("sim_ticks", 0) or 0)"""
if old in text and "exact_phase_counts =" not in text:
    text = text.replace(old, new)
old = """        component_phases.append({
            "phase_index": int(phase.get("phase_index", len(component_phases))),
            "sim_ticks": phase_ticks,
            "sim_cycles": phase_cycles,
            "total_packets": int(phase.get("total_packets", 0) or 0),
            "vnet_packets": {
                str(int(k)): int(v)
                for k, v in (phase.get("vnet_packets") or {}).items()
            },
            "vnet_flits": {
                str(int(k)): int(v)
                for k, v in (phase.get("vnet_flits") or {}).items()
            },
            "source_fractions": source_fractions,
        })"""
new = """        phase_index = int(phase.get("phase_index", len(component_phases)))
        component_phase = {
            "phase_index": phase_index,
            "sim_ticks": phase_ticks,
            "sim_cycles": phase_cycles,
            "total_packets": int(phase.get("total_packets", 0) or 0),
            "vnet_packets": {
                str(int(k)): int(v)
                for k, v in (phase.get("vnet_packets") or {}).items()
            },
            "vnet_flits": {
                str(int(k)): int(v)
                for k, v in (phase.get("vnet_flits") or {}).items()
            },
            "source_fractions": source_fractions,
        }
        if exact_phase_counts.get(phase_index):
            exact_counts = int_nested_flit_counts(exact_phase_counts[phase_index])
            component_phase["src_dst_ni_flits_counts_by_vnet"] = exact_counts
            component_phase["src_dst_ni_bytes_counts_by_vnet"] = (
                nested_flits_to_bytes(exact_counts, source_flit_size))
        component_phases.append(component_phase)"""
if old in text and "component_phase =" not in text:
    text = text.replace(old, new)
builder.write_text(text)
