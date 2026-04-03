# Architecture

## Goal

Convert clang `-ftime-trace` output into a workflow that can be inspected with normal
`perf report` tooling.

## High-level pipeline

1. Wrap a direct `clang` or `clang++` compile command
2. Ensure `-ftime-trace` is enabled
3. Run the compile and collect the trace JSON
4. Load and normalize clang time-trace events
5. Reconstruct a compiler-oriented call tree
6. Convert self time into a synthetic replay workload
7. Emit LLVM IR for the replay tree
8. Compile the replay helper
9. Run `perf record` on the helper to produce a real `perf.data`
10. Capture a smoke `perf report` output

## Why replay instead of writing `perf.data` directly

The risky requirement is not just exporting data, but making the result behave like real perf.
The chosen v1 route is:

- reconstruct the compiler call tree from clang time-trace
- replay that tree in a helper binary
- let `perf record` create the final `perf.data`

This keeps the output perf-native while avoiding a custom `perf.data` writer.

## Module boundaries

### `command.py`

Owns direct-command validation and trace-path derivation.

### `trace_loader.py`

Owns clang JSON parsing and event normalization.

### `reconstruct.py`

Owns interval nesting, phase classification, and synthetic phase grouping such as:

- `clang frontend`
- `template instantiation`
- `codegen`

### `sampling.py`

Owns the conversion from time-based self cost to replay loop counts.

### `perf_writer.py`

Owns the replay IR, replay helper compilation, and `perf record` / `perf report` interaction.

### `pipeline.py`

Owns the end-to-end orchestration and compatibility wrapper API.

## Known limitations

- v1 primarily uses complete `"X"` time-trace events
- unmatched `b/e` trace pairs are not reconstructed
- the final perf profile is synthetic/replayed, not a real sampled compiler execution
- non-clang, non-Linux, and build-system interception are intentionally out of scope
