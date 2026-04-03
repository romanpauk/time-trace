# time-trace

[![CI](https://github.com/romanpauk/template-profiler/actions/workflows/ci.yml/badge.svg)](https://github.com/romanpauk/template-profiler/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)

`time-trace` is a Python CLI for turning clang `-ftime-trace` output into a profile you can
inspect with the usual `perf report` workflow.

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
