# Garnet Conformance Strategy

The production rule is simple: `pace-new/src` is a byte-identical mirror of
`gem5-25.1/src/mem/ruby/network/garnet`. Do not edit files in `pace-new/src`.
All standalone runtime, Ruby emulation, build glue, and optimizations belong
outside that directory.

## Gates

1. Byte identity: every tracked Garnet file must match gem5 by SHA-256.
2. gem5 ground truth: run `Garnet_standalone` synthetic traffic trials and keep
   stats and traces as the reference output.
3. pace-new standalone: run the same trials through the standalone Ruby
   compatibility layer.
4. Trace equality: compare canonical event traces, not just aggregate stats.
5. Performance: optimize only after gates 1-4 pass, and keep them in CI.

## Trace Logging Without Breaking Byte Identity

Do not permanently add logging to `pace-new/src`. Use one of these methods:

- The standalone compatibility layer supports opt-in JSONL tracing with
  `--trace-jsonl <path>`. This records runtime object construction, topology
  wiring, event-queue scheduling/wakeup, message-buffer enqueue/dequeue,
  synthetic injection, synthetic delivery, and simulation completion without
  touching byte-identical Garnet files.
- The reversible gem5 trace patch records deeper Garnet pipeline events in a
  trace build: NI flitisization/ejection, router wakeups, input-unit flit
  arrival and route compute, switch allocator requests/grants, VC allocation,
  crossbar traversal, output-unit enqueue, link transfer, and credit send/
  receive/increment/decrement.
- Prefer existing gem5 debug flags where they are complete enough.
- Otherwise generate an instrumented temporary source tree from a patch that is
  applied identically to gem5 and pace-new for trace builds only.
- The conformance suite must first verify the production byte identity, then
  build the temporary instrumented trees and compare their traces.

The trace patch itself can be versioned, but the production Garnet files remain
unmodified.

The current gem5 trace-build workflow is:

```sh
python3 tools/gem5_trace_patch.py apply /gem5
scons build/Garnet_standalone/gem5.debug -j$(nproc)
python3 tools/run_conformance.py --with-gem5-trace
```

The patcher stores `*.pace_trace.bak` files beside each edited gem5 file. To
return the gem5 source tree to its pre-trace state:

```sh
python3 tools/gem5_trace_patch.py restore /gem5
```

## Minimum Trace Events

The trace must include enough state to replay and diagnose divergence:

- message-buffer enqueue, dequeue, stall, and callback registration
- NI flitisization, VC allocation, credit receipt, flit injection/ejection
- link transfer and bridge serialization/deserialization
- router input-unit state transition and route compute
- switch allocator requests, grants, and VC/order decisions
- output-unit credit changes
- crossbar traversal
- flit identity, packet id, vnet, vc, type, source, destination, route, width,
  enqueue/dequeue/set time, and hops

`verif/trials/garnet_deep_trace_matrix.json` is the current deterministic
deep-trace matrix. It covers forced vnet 0, forced vnet 1, forced multi-flit
vnet 2 data, all-source same-cycle contention into one destination, and longer
4x4 mesh paths for both control and data packets.

`tools/compare_deep_traces.py` compares internal Garnet pipeline events between
gem5 and pace-new for every matrix trial. The comparison intentionally ignores
wrapper/tester events and wall-clock tick scale, normalizes arbitrary packet-id
assignment by stable packet identity, and compares per-cycle event sets with
event-specific Garnet fields for NI, link, router, input-unit, switch
allocator, VC, crossbar, output-unit, and credit events.

The comparator now writes deterministic canonical proof artifacts when called
with `--canonical-dir`:

```text
gem5.canonical.jsonl
pace.canonical.jsonl
```

Those canonical JSONL files are sorted, normalized, and compared
byte-for-byte. Raw debug logs are not byte-compared because they contain
irrelevant wrapper noise, path/build differences, and arbitrary identifiers.
The proof target is exact byte equality after canonicalization.

`tests/test_deep_trace_compare.py` writes these canonical artifacts under:

```text
verif/out/deep_trace_canonical/<trial>/
```

Aggregate stats alone are not sufficient. Matching stats can hide divergent
intermediate behavior.

## Topology-General Coverage

`tests/test_topology_matrix.py` is the current topology-general validation
layer. It does not replace gem5 deep trace comparison, but it extends the
standalone replay validator beyond plain meshes.

Current topology matrix cases:

- `chiplet_2p5d`: interposer-style chiplet links, heterogeneous link widths,
  CDC/SerDes metadata, and cross-chiplet replay delivery.
- `chiplet_3d_stack`: stacked layers, `Up`/`Down` links, heterogeneous clocks
  and widths, CDC/SerDes metadata, and cross-layer replay delivery.
- `irregular_nonmesh`: explicit non-mesh graph, custom port names,
  heterogeneous clocks and widths, CDC/SerDes metadata, supported-vnet
  restricted links, and replay delivery on vnets 0/1/2.

Run it directly:

```sh
python3 tests/test_topology_matrix.py
```

It is also part of `tools/run_conformance.py --tier standard` and above.
