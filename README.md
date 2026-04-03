# time-trace

[![CI](https://github.com/romanpauk/template-profiler/actions/workflows/ci.yml/badge.svg)](https://github.com/romanpauk/template-profiler/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)

`time-trace` wraps a direct clang compile, reads clang's time-trace JSON, and
writes a synthetic `perf.data` file that can be inspected with normal perf
commands.

## Example

Compile a template-heavy source file through `time-trace`, keep only template
events, then open the resulting profile with normal perf tooling. From the
repository root, these commands are copy-pasteable as written:

```bash
uv run time-trace --output .time-trace-example --include "tag:template" -- clang++ -std=c++20 -c tests/cpp_samples/variant_visit.cpp -o variant_visit.o
perf report --stdio --percent-limit 0 --call-graph caller -i .time-trace-example/perf.data --sort symbol
```

```text
clang++ compilation
`--template
   `--VariantDispatcher<std::variant<...>>::run
      `--std::visit<Overloaded<...>, const std::variant<...>&>
         `--std::__do_visit<...>
```

You can also look at individual template symbols by inclusive samples:

```bash
perf report --stdio -i .time-trace-example/perf.data --sort symbol --fields overhead_children,overhead,symbol
```

```text
Children   Self  Symbol
17.35%     6.62% PerformPendingInstantiations
18.93%     0.63% VariantDispatcher<std::variant<...>>::run
17.67%     1.26% std::visit<Overloaded<...>, const std::variant<...>&>
11.99%     0.63% std::variant<VariantPayload<...>>::variant<VariantPayload<int>, ...>
11.36%     0.00% std::variant<VariantPayload<...>>::variant<0UL, VariantPayload<int>, ...>
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
uv run time-trace --output .time-trace-example --include "tag:template" -- clang++ -std=c++20 -c tests/cpp_samples/variant_visit.cpp -o variant_visit.o
perf report --stdio --percent-limit 0 --call-graph caller -i .time-trace-example/perf.data --sort symbol
```

## Docs

- [`docs/usage.md`](docs/usage.md) — commands to run, generated artifacts, and example `perf report` / `perf script` workflows
- [`docs/development.md`](docs/development.md) — local setup, project layout, and the main files to read when changing the tool
- [`docs/architecture.md`](docs/architecture.md) — how trace reconstruction, sampling, symbol generation, and `perf.data` writing fit together
