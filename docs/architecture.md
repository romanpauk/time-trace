# Architecture

The tool reads clang time-trace JSON and produces a `perf.data` file that works
with normal perf commands.

## Pipeline

1. rewrite the incoming clang command to add `-ftime-trace`
2. run the compile
3. load the emitted JSON trace
4. reconstruct a compiler call tree with synthetic phase roots
5. choose chronological sample timestamps across the trace and resolve the active compiler stack at each point
6. build a synthetic symbol image for those frames
7. write `perf.data`

## Trace reconstruction

Clang time-trace events are loaded as intervals with start and duration
information. Reconstruction builds a nested tree from those intervals and keeps
synthetic phase roots such as frontend, template instantiation, or codegen when
that makes the result easier to navigate.

Sampling is timeline-aware. The tool chooses sample timestamps across the full
trace duration and resolves the active stack at each timestamp. That gives the
written `perf.data` file chronological synthetic samples instead of a flat list
of weighted symbols.

The tree stays narrow by limiting the number of retained nodes. When the trace
is larger than the configured maximum, reconstruction prunes lower-priority
subtrees while keeping the main hot paths visible.

## Synthetic symbols

The generated `perf.data` points at a synthetic shared object with one symbol per
sampled frame name. Symbol names come from the reconstructed compiler frames,
for example `clang frontend`, `template instantiation`, or a concrete template
instantiation such as `ValueAt<100, ValueList<...>>`.

The synthetic image gives perf normal symbol lookup inputs, so `perf report` and
`perf script` can show names without any custom viewer.

## Perf data layout

The emitted file uses a narrow subset of perf records:

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

That is enough for:

- `perf report --stdio`
- caller-oriented call graphs
- callee-oriented call graphs
- `perf script`

## Platform support

The writer currently supports:

- Linux
- little-endian `x86_64`
- clang / clang++ input
- `nm`, the generated synthetic image, and `perf` for downstream inspection
