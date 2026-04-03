# time-trace

[![CI](https://github.com/romanpauk/template-profiler/actions/workflows/ci.yml/badge.svg)](https://github.com/romanpauk/template-profiler/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)

`time-trace` wraps a direct clang compile, reads clang's time-trace JSON, and
writes a synthetic `perf.data` file that can be inspected with normal perf
commands.

A run looks like this:

```bash
uv run time-trace -- clang++ -std=c++20 -c tests/cpp_samples/variant_visit.cpp -o variant_visit.o
perf report --stdio -i time-trace-out/variant_visit-.../perf.data --sort symbol
```

```text
100.00%   1.75%  clang++ compilation
          |--91.64%--clang frontend
          |          template instantiation [8]
          |          |--8.64%--VariantDispatcher<...>::run
          |          |           --7.94%--std::visit<Overloaded<...>, const std::variant<...>&>
```

## Quick start

Requirements: `clang`/`clang++`, `perf`, and `nm` must be available on `PATH`, and the direct writer currently supports Linux on little-endian `x86_64` only.

```bash
uv sync --all-groups
uv run time-trace -- clang++ -std=c++20 -c sample.cpp -o sample.o
```

## Docs

- `docs/usage.md` — CLI usage, generated artifacts, and example `perf report` / `perf script` output
- `docs/development.md`
- `docs/architecture.md`
