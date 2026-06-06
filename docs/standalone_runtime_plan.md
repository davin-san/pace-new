# Standalone Runtime Plan

`pace-new/src` stays byte-identical to gem5 Garnet. The standalone simulator is
the compatibility layer that builds gem5-style Ruby objects, clocks them, and
feeds them messages.

## Current Checkpoint

- Garnet source mirror: byte-identical to
  `gem5-25.1/src/mem/ruby/network/garnet`.
- Build surface: all copied Garnet `.cc` files compile unchanged through
  `compat/include` and `compat/src`.
- Executable: `pace-new` instantiates Garnet from topology JSON and can run
  synthetic traffic with optional JSONL tracing via `--trace-jsonl`.
- Conformance: current suite passes byte identity, topology generation, runtime
  instantiation, packet movement, trace generation, pace synthetic smoke, and
  gem5 synthetic smoke runs. The optional gem5 trace-build gate also passes
  when the Docker gem5 tree is patched with `tools/gem5_trace_patch.py`, and
  the deterministic deep internal Garnet trace matrix compares equal between
  gem5 and a temporary trace-instrumented pace worktree.

## Next Implementation Stages

1. Replace the placeholder `main` with a small command-line driver matching the
   fields used by gem5 `garnet_synth_traffic.py`: CPUs, dirs, topology,
   mesh rows, sim cycles, synthetic pattern, injection rate, vnet, and seed.
   The Python config entry point now exists at
   `configs/example/garnet_synth_traffic.py` and emits the canonical network
   JSON for the C++ runtime.
2. Build a Ruby compatibility object graph that constructs:
   - `GarnetNetwork`
   - `GarnetRouter`
   - `GarnetExtLink`
   - `GarnetIntLink`
   - `GarnetNetworkInterface`
   - per-vnet `MessageBuffer` pairs
   The object graph now instantiates `GarnetNetwork`, routers, network
   interfaces, ext/int links, network links, credit links, and HeteroGarnet
   bridges from topology JSON. Message-buffer wiring and traffic injection are
   now exist for Garnet_standalone synthetic traffic.
3. Implement the topology builder outside `src`, starting with `Mesh_XY`.
   Routing tables and link weights must match gem5 topology output exactly.
   `Mesh_XY` is ported with gem5 link ordering. `HeteroChiplet` is the first
   data-driven topology for 2.5D/3D packages and carries chiplet/layer/width/
   clock-domain metadata through routers and links.
   The C++ compatibility `Topology` now creates Garnet links through unchanged
   `GarnetNetwork::makeExtInLink`, `makeExtOutLink`, and `makeInternalLink`
   using gem5-style shortest-path routing tables.
4. Implement the synthetic traffic source outside `src`, using the same packet
   sizing, vnet selection, destination selection, injection-rate semantics, and
   random seed behavior as gem5.
   The first C++ synthetic driver injects through NI protocol buffers, uses
   8-byte control messages for vnets 0/1 and 72-byte data messages for vnet 2,
   supports gem5 traffic pattern names, single sender/destination, injection
   rate, packet caps, and drains delivered directory messages. Exact gem5 RNG
   parity is still pending trace work.
5. Extend `tools/run_conformance.py` so every trial runs both gem5 and
   `pace-new`, then compares canonical outputs.
   Current gates include byte identity, Python topology generation, C++
   runtime instantiation for `Mesh_XY` and a heterogeneous 3D chiplet package,
   packet movement through vnet 0 control and vnet 2 data packets, standalone
   trace generation, pace synthetic smoke runs, and gem5 synthetic smoke runs.
   `tools/run_pace_synth.py` now writes canonical `pace.garnet.stats.v1` JSON
   for each pace trial and can also write `trace.jsonl` with `--trace`.
   Runtime stat/trace equality with gem5 is next; the stock gem5 smoke stats
   are not yet a sufficient packet-level oracle without gem5-side trace
   instrumentation.
6. Add trace-build support using temporary instrumentation patches. Production
   source identity must run before any trace build is generated.
   The reversible gem5 patch now emits `PACE_TRACE` JSON payloads for synthetic
   traffic injection/completion, Ruby `MessageBuffer` enqueue/dequeue, NI
   flitisization/ejection, router wakeups, input-unit route compute and buffer
   insertion, switch allocator requests/grants, VC allocation, crossbar
   traversal, output-unit enqueue, link transfer, and credit send/receive/
   increment/decrement. `tools/extract_gem5_trace.py` converts the gem5 debug
   stream into canonical JSONL, and `tests/test_gem5_trace_generation.py`
   validates deterministic deep-pipeline coverage for the trace matrix.
   `tools/pace_trace_patch.py` applies the same internal
   Garnet trace points to a temporary pace worktree, and
   `tools/compare_deep_traces.py` checks per-cycle field-level equality for
   the internal Garnet pipeline. The matrix covers vnets 0/1/2, multi-flit
   data, same-cycle source contention, and 4x4 long paths. The compatibility
   event queue now uses gem5-style same-tick priority categories for data
   links, routers, network interfaces, and credit links.
7. Only after trace equality is stable, optimize compatibility allocation,
   scheduling, statistics, and message storage. Garnet files remain untouched.

## Non-Negotiable Gates

- `pace-new/src` byte identity must pass before and after every runtime change.
- A runtime change is not complete until the conformance matrix includes both
  gem5 and `pace-new` for the affected trial.
- Any performance optimization must preserve byte identity and trace equality.
