# Development

## Tooling

This project uses:

- `uv` for environment and dependency management
- `pytest` for tests
- `ruff` for linting and formatting
- `mypy` for type checking

## Setup

```bash
uv sync --all-groups
```

## Common commands

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check src tests
uv run mypy src tests
uv build
```

## GitHub Actions

CI lives in `.github/workflows/ci.yml`.

It currently runs:

- `uv sync --all-groups`
- `uv run ruff check .`
- `uv run ruff format --check src tests`
- `uv run mypy src tests`
- `uv run pytest -m "not integration"`
- `uv build`

The workflow intentionally skips integration tests because the current end-to-end perf tests
depend on local `clang`/`perf` availability and perf permissions that are not guaranteed in a
default GitHub-hosted runner.

## Project structure

- `src/time_trace/cli.py` — CLI parsing and entrypoint
- `src/time_trace/command.py` — compile-command validation and wrapping
- `src/time_trace/trace_model.py` — typed data structures
- `src/time_trace/trace_loader.py` — clang time-trace loading and normalization
- `src/time_trace/reconstruct.py` — compiler call-tree reconstruction
- `src/time_trace/sampling.py` — self-time to replay-budget conversion
- `src/time_trace/perf_writer.py` — replay emission and perf capture
- `src/time_trace/pipeline.py` — end-to-end orchestration
- `tests/` — unit and integration tests

## Testing strategy

The test suite includes:

- unit tests for command wrapping, loading, reconstruction, and replay planning
- smoke tests for replay generation and perf ingestion
- end-to-end tests running a tiny real `clang++` compilation through the pipeline

## Documentation contract

Keep the top-level `README.md` short and navigational. Put detailed usage, development, and
design notes in `docs/`.
