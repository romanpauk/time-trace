# Usage

## Entry points

The package installs two equivalent console scripts:

- `time-trace`
- `time-trace.py`

Both call the same `time_trace.cli:main` entrypoint.

## Basic invocation

```bash
uv run time-trace --output artifacts --keep-trace \
  clang++ -std=c++20 -c sample.cpp -o sample.o
```

For development you can also use:

```bash
uv run time-trace.py clang++ -std=c++20 -c sample.cpp -o sample.o
```

## CLI shape

```text
time-trace [tool-options] -- clang++ [compile-options]
time-trace [tool-options] clang++ [compile-options]
```

The wrapper expects a direct `clang` or `clang++` command and automatically adds
`-ftime-trace` when it is missing.

## Important options

- `--output <dir>` — where generated artifacts go
- `--keep-trace` — keep the raw clang JSON trace
- `--emit-intermediate` — keep replay IR and helper binary
- `--max-nodes <n>` — cap reconstructed call-tree size
- `--target-iterations <n>` — replay loop budget for relative cost scaling
- `--sample-frequency <n>` — pass an explicit sampling frequency to `perf record`
- `--replay-compiler <path>` — compiler used for the replay helper
- `--perf-binary <path>` — `perf` executable to use
- `--verbose` — print more artifact paths

## Generated artifacts

Typical output:

- `perf.data` — the main artifact for `perf report`
- `perf-report.txt` — a non-interactive smoke report captured during generation
- `<compile-output>.json` — clang time-trace JSON when `--keep-trace` is enabled
- `replay.ll` and `replay-helper` — replay intermediates when `--emit-intermediate` is enabled

## Perf workflow

Inspect the generated artifact with the normal `perf report` flow:

```bash
perf report --stdio -i artifacts/perf.data --sort symbol
```

Success looks like a normal `perf report` output that includes reconstructed compiler frames
such as:

- `clang frontend`
- `template instantiation`
- specific instantiation labels like `Foo<int>`
- `codegen`

This enables inclusive/self-cost sorting and caller/callee browsing in the standard perf UI.

## Troubleshooting

### `perf` cannot open the generated file

Check that:

- you are on Linux
- `perf` is installed and runnable
- the `perf.data` path is the generated file in the chosen output directory

### clang trace JSON was not found

The wrapper derives the trace path from `-o <output>` or the source file path. Make sure the
compiler command is a direct `clang`/`clang++` compile invocation and that the compile itself
succeeds.

### The report looks synthetic

That is expected for v1. The tool reconstructs a compiler call tree from clang time-trace data,
then replays it into a real `perf.data` file so the normal perf workflow can be used.
