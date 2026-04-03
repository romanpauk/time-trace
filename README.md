# time-trace

[![CI](https://github.com/romanpauk/template-profiler/actions/workflows/ci.yml/badge.svg)](https://github.com/romanpauk/template-profiler/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)

`time-trace` is a typed Python CLI that wraps a direct `clang` / `clang++` compile command,
captures the resulting `-ftime-trace` JSON, reconstructs a compiler-oriented call tree, and
hands that reconstructed workload to `perf` so you can inspect it with the usual
`perf report` workflow.

## Documentation

- [Usage guide](docs/usage.md)
- [Development guide](docs/development.md)
- [Architecture notes](docs/architecture.md)

## Requirements

- Linux
- `clang` / `clang++`
- `perf`
- Python 3.12+
- `uv`

## Quick start

```bash
uv sync --all-groups
uv run time-trace --output artifacts --keep-trace \
  clang++ -std=c++20 -c sample.cpp -o sample.o
```

Inspect the generated profile with:

```bash
perf report --stdio -i artifacts/perf.data --sort symbol
```

## What it produces

- `perf.data` for normal `perf report` workflows
- `perf-report.txt` as a captured smoke report
- optional raw clang trace JSON with `--keep-trace`
- optional replay intermediates with `--emit-intermediate`

## Scope for v1

- direct wrapper around `clang` / `clang++`
- Linux only
- clang time-trace input only
- no build-system interception

## Repository layout

- `src/time_trace/` — implementation
- `tests/` — unit and integration coverage
- `docs/` — usage, development, and architecture documentation
