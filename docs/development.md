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

- `src/time_trace/command.py` — clang command wrapping
- `src/time_trace/trace_loader.py` — clang JSON loading
- `src/time_trace/reconstruct.py` — call-tree reconstruction
- `src/time_trace/sampling.py` — synthetic sample planning
- `src/time_trace/elf_writer.py` — synthetic ELF generation
- `src/time_trace/perf_data_model.py` — direct perf.data packing
- `src/time_trace/perf_writer.py` — perf artifact writing and validation
- `src/time_trace/pipeline.py` — end-to-end orchestration
- `tests/` — unit and integration coverage

## Test split

- unit tests for command wrapping, loading, reconstruction, sample planning, and direct perf-data writing
- integration tests for tiny clang traces and perf ingestion

## Notes

The current implementation writes `perf.data` directly. It does not call
`perf record` or use a locally captured seed file. It also expects `nm` to be
available so it can map symbol offsets in the synthetic shared object.
