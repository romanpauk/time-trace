# time-trace

[![CI](https://github.com/romanpauk/template-profiler/actions/workflows/ci.yml/badge.svg)](https://github.com/romanpauk/template-profiler/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)

`time-trace` wraps a direct clang compile, reads clang's time-trace JSON, and
writes a synthetic `perf.data` file that can be inspected with normal perf
commands.

## Example

Compile a template-heavy source file through `time-trace`, then open the
resulting profile with normal perf tooling. From the repository root, these
commands are copy-pasteable as written:

```bash
uv run time-trace --output .time-trace-example -- clang++ -std=c++20 -c tests/cpp_samples/variant_visit.cpp -o variant_visit.o
perf report --stdio -i .time-trace-example/perf.data --sort symbol
```

```text
100.00%   1.75%  clang++ compilation
          |--91.64%--clang frontend
          |          |--16.40%--template instantiation [8]
          |          |          |--8.64%--VariantDispatcher<std::variant<...>>::run
          |          |          |           --7.94%--std::visit<Overloaded<...>, const std::variant<...>&>
          |          |--8.77%--template instantiation [9]
```

You can also look at individual template symbols by inclusive samples:

```bash
perf report --stdio -i .time-trace-example/perf.data --sort symbol --fields overhead_children,overhead,symbol
```

```text
Children   Self  Symbol
48.81%     0.60% ValueAt<100, ValueList<...>>
48.21%     0.60% ValueAt<99, ValueList<...>>
47.62%     0.60% ValueAt<98, ValueList<...>>
16.40%     0.54% template instantiation [8]
 8.64%     0.27% VariantDispatcher<std::variant<...>>::run
```

These examples are abridged from real runs of the sample programs in
`tests/cpp_samples/`.

That is the point of the tool: turn clang's trace into something you can browse
with the usual perf workflow.

## Quick start

Runtime requirements: `clang`/`clang++` and `nm` must be available on `PATH`.
The tool supports Linux on little-endian `x86_64` only.

To inspect the generated profile with the normal perf tools, `perf` must also be
available on `PATH`.

```bash
uv run time-trace --output .time-trace-example -- clang++ -std=c++20 -c tests/cpp_samples/variant_visit.cpp -o variant_visit.o
perf report --stdio -i .time-trace-example/perf.data --sort symbol
```

## Docs

- [`docs/usage.md`](docs/usage.md) — commands to run, generated artifacts, and example `perf report` / `perf script` workflows
- [`docs/development.md`](docs/development.md) — local setup, project layout, and the main files to read when changing the tool
- [`docs/architecture.md`](docs/architecture.md) — how trace reconstruction, sampling, symbol generation, and `perf.data` writing fit together
