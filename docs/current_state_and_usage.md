# pace-new Current State And Usage

This document records the current `pace-new` checkpoint after the Garnet
standalone, replay, conformance, benchmark, and first generic runtime
optimization work.

## Core Rule

`pace-new/src` is the production Garnet logic and must stay byte-identical to
`gem5-25.1/src/mem/ruby/network/garnet`.

Do not edit `pace-new/src` for standalone support or performance work. Runtime
support, Ruby compatibility objects, validators, replay drivers, benchmarks,
and optimizations belong in:

- `pace-new/compat`
- `pace-new/configs`
- `pace-new/tools`
- `pace-new/tests`
- `pace-new/docs`

The conformance suite checks this with SHA-256 byte identity before the runtime
tests.

## What Exists Now

The current executable is `pace-new/pace-new`. It builds byte-identical Garnet
sources with a compatibility layer that supplies the minimum gem5/Ruby
infrastructure needed to instantiate and run Garnet without gem5.

Current capabilities:

- Instantiate Garnet networks from gem5-style topology JSON.
- Generate topology JSON from Python config files modeled after gem5 configs.
- Run standalone synthetic traffic.
- Run deterministic replay schedules.
- Emit JSON stats artifacts.
- Emit JSONL compatibility traces with `--trace-jsonl`.
- Validate byte identity against gem5 Garnet.
- Validate topology generation and runtime instantiation.
- Validate packet movement through Garnet.
- Validate deterministic replay schedules.
- Validate replay through representative 2.5D, 3D, heterogeneous, and
  irregular non-mesh package topologies.
- Compare deep internal Garnet traces against gem5 trace builds.
- Benchmark `pace-new` and `pace-lite` against identical replay files.

The first generic runtime optimization has also been applied:

- `compat/src/Topology.cc` now computes all-pairs shortest paths with a
  Floyd-Warshall pass instead of repeated global relaxation.
- This is generic topology logic, not mesh-specific.
- Full gem5-backed conformance passed after this change.

Measured impact on `mesh8x8-smoke` replay:

```text
before: pace-new best 0.1490s
after:  pace-new best 0.0595s
```

## Build

From `pace-new`:

```sh
make all
```

Clean rebuild:

```sh
make clean all
```

Useful build modes:

```sh
make all BUILD=release
make all BUILD=debug
make all BUILD=trace
make all BUILD=profile
```

On Windows, prefer running build/test commands through the Docker image used
for the project:

```sh
docker run --rm \
  -v unified-framework_gem5-source:/gem5:rw \
  -v "C:\Users\User\Documents\School\ORS\pace_stuff:/workspace:rw" \
  -w /workspace/pace-new \
  -e PYTHONDONTWRITEBYTECODE=1 \
  unified-framework-init-builder:latest \
  sh -lc 'make all'
```

## Generate A Topology

Example 4x4 mesh topology:

```sh
python3 configs/example/garnet_synth_traffic.py \
  --num-cpus 16 \
  --num-dirs 16 \
  --network garnet \
  --topology Mesh_XY \
  --mesh-rows 4 \
  --sim-cycles 1000 \
  --synthetic uniform_random \
  --injectionrate 0.01 \
  --output verif/out/example_mesh4x4/topology.json
```

Instantiate without traffic:

```sh
./pace-new --topology-json verif/out/example_mesh4x4/topology.json
```

Run synthetic traffic:

```sh
./pace-new \
  --topology-json verif/out/example_mesh4x4/topology.json \
  --simulate \
  --stats-json verif/out/example_mesh4x4/stats.json
```

Enable compatibility-layer trace output:

```sh
./pace-new \
  --topology-json verif/out/example_mesh4x4/topology.json \
  --simulate \
  --stats-json verif/out/example_mesh4x4/stats.json \
  --trace-jsonl verif/out/example_mesh4x4/trace.jsonl
```

## Replay Driver

Replay schedules are deterministic JSON files using schema
`pace.garnet.replay.v1`.

Generate the default shared 2x2 replay:

```sh
python3 tools/generate_replay.py \
  --scenario deterministic-mesh2x2 \
  --output verif/out/replay/deterministic-mesh2x2.replay.json
```

Run replay in `pace-new`:

```sh
./pace-new \
  --topology-json verif/out/replay/topology.json \
  --simulate \
  --replay-json verif/out/replay/deterministic-mesh2x2.replay.json \
  --stats-json verif/out/replay/stats.json
```

Replay scenarios currently available:

```text
deterministic-mesh2x2
mesh4x4-long-paths
mesh4x4-contention
multi-vnet
multi-flit
burst-injection
drain-edge-cases
mesh8x8-smoke
mesh4x4-multiflit-vnet0
```

List scenarios:

```sh
python3 tools/generate_replay.py --list
```

Generate all replay files for a tier:

```sh
python3 tools/generate_replay.py \
  --tier standard \
  --output verif/out/replay/standard
```

Replay tiers:

```text
quick    deterministic-mesh2x2
standard quick + long paths, contention, multi-vnet, multi-flit, burst, drain
stress   standard + mesh8x8-smoke and mesh4x4-multiflit-vnet0
```

## Topology Matrix

The topology matrix is the current validator for topology generality beyond
plain 2D meshes:

```sh
python3 tests/test_topology_matrix.py
```

Current cases:

```text
chiplet_2p5d
  uses configs/chiplets/example_2p5d.json
  validates interposer-style links, CDC/SerDes metadata, heterogeneous widths,
  and replay packet movement across chiplets

chiplet_3d_stack
  uses configs/chiplets/example_3d.json
  validates Up/Down links, stacked layers, heterogeneous widths/clocks,
  CDC/SerDes metadata, and replay packet movement across layers/chiplets

irregular_nonmesh
  uses configs/chiplets/irregular_nonmesh.json
  validates an explicit non-mesh graph with custom port names, asymmetric
  geometry, heterogeneous clocks/widths, CDC/SerDes metadata, supported-vnet
  restricted links, and replay packet movement over vnets 0/1/2
```

The topology matrix checks:

- generated topology features match the intended case
- topology instantiates in the standalone runtime
- replay packets inject and deliver
- per-vnet packet/flit stats match the replay file
- replay inject/deliver trace events match the replay file
- Garnet link utilization is positive

This does not prove every possible topology. It prepares representative
coverage for the classes we care about and provides a place to add new
topology families before relying on them.

## Conformance Tests

Main runner:

```sh
python3 tools/run_conformance.py --tier standard --skip-gem5
```

Tiers:

```text
quick
  byte identity
  topology generation
  runtime instantiation
  event queue
  packet movement
  trace generation
  shared replay
  pace synthetic smoke

standard
  quick
  topology matrix
  replay matrix

full
  standard
  gem5 synthetic smoke
  gem5 trace generation
  deep trace comparison

stress
  full behavior plus stress replay matrix when run directly
```

Full gem5-backed conformance command used at this checkpoint:

```sh
docker run --rm \
  -v unified-framework_gem5-source:/gem5:rw \
  -v "C:\Users\User\Documents\School\ORS\pace_stuff:/workspace:rw" \
  -w /workspace/pace-new \
  -e PYTHONDONTWRITEBYTECODE=1 \
  unified-framework-init-builder:latest \
  sh -lc 'python3 tools/run_conformance.py --tier full'
```

Latest verified full result:

```text
byte_identity: PASS
topology_generation: PASS
runtime_instantiation: PASS
event_queue: PASS
packet_movement: PASS
trace_generation: PASS
shared_replay: PASS
topology_matrix: PASS
replay_matrix: PASS
pace_synth_smoke: PASS
gem5_synth_smoke: PASS
gem5_trace_generation: PASS
deep_trace_compare: PASS
```

Stress replay matrix:

```sh
python3 tests/test_replay_matrix.py --tier stress
```

The replay matrix validates:

- final packet/flit stats
- per-vnet injected and delivered packet counts
- per-vnet injected and delivered flit counts
- exact `replay.inject` events against the replay file
- delivered destination/vnet/message-size/flit multiset
- positive Garnet link utilization

## Deep Trace Workflow

Production `pace-new/src` remains unmodified. Deep trace comparison uses
temporary instrumentation:

- `tools/gem5_trace_patch.py` patches the gem5 tree used for trace builds.
- `tools/pace_trace_patch.py` creates a temporary instrumented pace worktree.
- `tools/extract_gem5_trace.py` converts gem5 debug output into JSONL.
- `tools/compare_deep_traces.py` emits canonical internal Garnet JSONL files
  and byte-compares those canonical files.

Current deep-trace matrix:

```text
mesh2x2_single_packet_vnet0
mesh2x2_single_packet_vnet1
mesh2x2_single_packet_vnet2_data
mesh2x2_all_sources_to_dir3_vnet0
mesh2x2_all_sources_to_dir3_vnet2_data
mesh4x4_long_path_vnet0
mesh4x4_long_path_vnet2_data
```

Run the full gem5-backed trace gate through:

```sh
python3 tools/run_conformance.py --tier full
```

or explicitly:

```sh
python3 tools/run_conformance.py --with-gem5-trace
```

Canonical proof artifacts are written to:

```text
verif/out/deep_trace_canonical/<trial>/gem5.canonical.jsonl
verif/out/deep_trace_canonical/<trial>/pace.canonical.jsonl
```

These files are the byte-level oracle. Raw debug logs are not compared
byte-for-byte because they include irrelevant wrapper/debug noise and
environment-specific details. The canonical files normalize those details and
then require exact byte equality.

## Benchmarks

Replay matrix benchmark:

```sh
python3 tools/benchmark_runtime.py --suite replay-matrix --repeats 3
```

This builds both `pace-new` and `pace-lite`, generates identical replay files,
generates matching topologies where possible, and runs the common vnet0 replay
workloads:

```text
deterministic-mesh2x2
mesh4x4-long-paths
mesh4x4-contention
mesh4x4-multiflit-vnet0
mesh8x8-smoke
```

Latest measured best times after the generic topology optimization:

```text
scenario                     pace-new   pace-lite
deterministic-mesh2x2        0.0239s    0.0208s
mesh4x4-long-paths           0.0276s    0.0216s
mesh4x4-contention           0.0278s    0.0254s
mesh4x4-multiflit-vnet0      0.0255s    0.0239s
mesh8x8-smoke                0.0595s    0.0290s
```

The shared `pace-lite` replay comparison is intentionally vnet0-only because
that is the safe common semantic subset. `pace-new` and gem5 conformance cover
multi-vnet and vnet2 data behavior through the replay matrix and deep trace
matrix.

## Optimization Boundary

The current stopping point is deliberate:

- The main generic topology bottleneck was optimized.
- Full gem5-backed conformance passed after the change.
- `pace-new/src` remains byte-identical to gem5 Garnet.
- Remaining single-run latency gap is mostly the cost of keeping gem5-style
  topology/routing object construction.

Avoid mesh-specific fast paths unless the project explicitly decides to trade
generality for a dedicated topology implementation. Future preferred
optimization surfaces are generic:

- topology build caching keyed by topology JSON hash
- batch execution that reuses an instantiated topology across trials
- flatter generic topology data structures
- faster schema-specific topology JSON loading

Any future optimization must pass:

```sh
python3 tools/run_conformance.py --tier standard --skip-gem5
python3 tests/test_topology_matrix.py
python3 tests/test_replay_matrix.py --tier stress
python3 tools/run_conformance.py --tier full
```

The full tier is the final guardrail for changes that can affect routing,
event timing, packet movement, or Garnet-visible behavior.
