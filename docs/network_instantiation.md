# Network Instantiation

Network construction follows gem5's topology pattern:

```text
topology.makeTopology(options, network, IntLink, ExtLink, Router)
```

`configs/example/garnet_synth_traffic.py` is the current entry point. It
creates Garnet_standalone controllers, imports a topology from
`configs/topologies`, and emits a canonical JSON object graph for the C++
runtime.

## Mesh Example

```sh
python3 configs/example/garnet_synth_traffic.py \
  --num-cpus=16 \
  --num-dirs=16 \
  --network=garnet \
  --topology=Mesh_XY \
  --mesh-rows=4 \
  --sim-cycles=1000 \
  --synthetic=uniform_random \
  --injectionrate=0.01 \
  --output=verif/out/pace/mesh4x4/topology.json
```

## Heterogeneous Chiplet Example

```sh
python3 configs/example/garnet_synth_traffic.py \
  --num-cpus=4 \
  --num-dirs=4 \
  --network=garnet \
  --topology=HeteroChiplet \
  --chiplet-spec=configs/chiplets/example_3d.json \
  --sim-cycles=1000 \
  --synthetic=uniform_random \
  --injectionrate=0.01 \
  --output=verif/out/pace/hetero3d/topology.json
```

## Schema Contract

The JSON schema is `pace.garnet.network.v1`. It contains:

- `controllers`: Garnet_standalone L1 and directory controller nodes.
- `routers`: router id, latency, width, x/y/z coordinates, chiplet id, and
  clock domain.
- `ext_links`: bidirectional controller-router links expressed with gem5-style
  `ExtLink` fields plus CDC/SerDes flags.
- `int_links`: unidirectional router-router links expressed with gem5-style
  `IntLink` fields plus CDC/SerDes flags, width, latency, weight, and optional
  supported vnets.

The C++ runtime consumes the generated JSON directly:

```sh
make all
./pace-new --topology-json verif/out/pace/mesh4x4/topology.json
```

To run the current synthetic traffic path:

```sh
./pace-new --topology-json verif/out/pace/mesh4x4/topology.json --simulate
```

To preserve a canonical stats artifact:

```sh
./pace-new \
  --topology-json verif/out/pace/mesh4x4/topology.json \
  --simulate \
  --stats-json verif/out/pace/mesh4x4/stats.json
```

At this stage the runtime constructs and initializes the Garnet object graph,
injects synthetic messages through NI protocol buffers, drives the event queue,
and drains delivered directory messages. Event-trace comparison against gem5 is
the next layer.

`HeteroChiplet` supports:

- 2.5D multi-chiplet packages through explicit interposer links.
- 3D stacks through per-chiplet `layers` and generated `Up`/`Down` links.
- heterogeneous widths through per-chiplet and per-link `width`.
- heterogeneous clocks through `clock_domain`, setting CDC flags where needed.
- explicit controller placement by node id or `Type:version`.
