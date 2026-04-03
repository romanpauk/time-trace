# Development

## Setup

Runtime tools needed on `PATH`: `clang` or `clang++`, `perf`, and `nm`.

```bash
uv sync --all-groups
```

## Common commands

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src tests
uv run pytest
```

## Project structure

- [`src/time_trace/command.py`](../src/time_trace/command.py) — clang command rewriting and output-path detection
- [`src/time_trace/trace_loader.py`](../src/time_trace/trace_loader.py) — clang JSON loading and event normalization
- [`src/time_trace/reconstruct.py`](../src/time_trace/reconstruct.py) — tree reconstruction and synthetic phase grouping
- [`src/time_trace/sampling.py`](../src/time_trace/sampling.py) — timeline-aware sample planning
- [`src/time_trace/elf_writer.py`](../src/time_trace/elf_writer.py) — synthetic shared object generation for perf symbolization
- [`src/time_trace/perf_data_model.py`](../src/time_trace/perf_data_model.py) — perf.data record packing
- [`src/time_trace/perf_writer.py`](../src/time_trace/perf_writer.py) — perf artifact writing and validation
- [`src/time_trace/pipeline.py`](../src/time_trace/pipeline.py) — end-to-end orchestration
- [`tests/`](../tests/) — coverage for CLI, reconstruction, sampling, perf output, and end-to-end sample programs

## Notes

`nm` must be available so the tool can map symbol offsets in the synthetic
shared object.
