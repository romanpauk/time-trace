# Architecture

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

The hard part is not exporting data. It is producing something that works well with normal perf
tools. The current approach is:

- reconstruct the compiler call tree from clang time-trace
- replay that tree in a helper binary
- let `perf record` create the final `perf.data`

This keeps the output in a standard perf format without implementing a custom `perf.data` writer.

## Module boundaries

### `command.py`

Handles command validation and trace-path derivation.

### `trace_loader.py`

Loads clang JSON and normalizes events.

### `reconstruct.py`

Builds the call tree, classifies phases, and inserts grouped phase nodes such as:

- `clang frontend`
- `template instantiation`
- `codegen`

### `sampling.py`

Converts self time into replay loop counts.

### `perf_writer.py`

Generates replay IR, builds the helper binary, and runs `perf record` / `perf report`.

### `pipeline.py`

Runs the full pipeline and provides the compatibility wrapper API.
