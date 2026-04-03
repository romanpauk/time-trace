# Architecture

The tool has one job: turn clang time-trace data into a `perf.data` file that
works with normal perf commands.

## Current pipeline

1. Rewrite the incoming clang command to add `-ftime-trace`
2. Run the compile
3. Load the emitted JSON trace
4. Reconstruct a compiler call tree with synthetic phase roots
5. Choose chronological sample timestamps across the trace and resolve the active compiler stack for each one
6. Build a synthetic ELF with one symbol per sampled frame
7. Write `perf.data` directly
8. Validate the result with `perf report` and `perf script`

## Direct writer contract

The current writer targets a narrow compatibility window:

- Linux
- x86_64
- clang / clang++ front-end input
- modern `perf` user tools that understand `PERFILE2`

The emitted file keeps the subset small:

- one event attribute
- one event id
- one `COMM` record
- one `MMAP2` record
- sample records with:
  - IP
  - TID
  - TIME
  - ID
  - CPU
  - PERIOD
  - CALLCHAIN

That subset is enough for:

- `perf report --stdio`
- caller-oriented call graphs
- callee-oriented call graphs
- `perf script`

## Main modules

### `command.py`
Wraps a direct clang command and infers the expected time-trace JSON path.

### `trace_loader.py`
Loads clang `X` events from the JSON trace and normalizes display labels.

### `reconstruct.py`
Builds a call tree, injects synthetic phase roots, preserves chronological structure,
and prunes the result to the configured node budget.

### `sampling.py`
Converts the reconstructed tree into timeline-aware synthetic samples. Each sample
uses a chronological timestamp and the active leaf-to-root callchain at that point.

### `elf_writer.py`
Builds a synthetic shared object that contains one exported symbol for each
sampled frame name.

### `perf_data_model.py`
Owns the direct `perf.data` layout and record packing.

### `perf_writer.py`
Combines the synthetic ELF and sampled callchains into a `perf.data` file, then
runs the validation commands that the rest of the tool relies on.
