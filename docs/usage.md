# Usage

## Basic invocation

```bash
time-trace clang++ -std=c++20 -c sample.cpp -o sample.o
```

The command:

1. adds `-ftime-trace`
2. runs clang
3. reconstructs a compiler call tree
4. writes a synthetic `perf.data`
5. validates it with perf

By default the tool prints the path to the generated `perf.data` file.

## Useful options

- `--output <dir>` — choose an output directory
- `--keep-trace` — copy the raw clang trace into the output directory
- `--emit-intermediate` — keep the synthetic LLVM IR that backs the symbol file
- `--max-nodes <n>` — limit the reconstructed tree size before sampling
- `--sample-frequency <hz>` — synthetic sampling frequency used for direct perf-data writing
- `--perf-binary <path>` — use a specific perf binary for validation
- `--verbose` — print the main artifact paths

## Generated artifacts

A normal run writes:

- `perf.data`
- `perf-report.txt`
- `perf-report-caller.txt`
- `perf-report-callee.txt`
- `perf-script.txt`
- `synthetic-image.so`

With `--emit-intermediate`, it also keeps:

- `synthetic-image.ll`

## Perf workflow

The generated file is meant for the normal perf tools:

```bash
perf report --stdio -i path/to/perf.data --sort symbol
perf report --stdio --call-graph caller -i path/to/perf.data --sort symbol
perf report --stdio --call-graph callee -i path/to/perf.data --sort symbol
perf script -i path/to/perf.data
```

### Example `perf report --stdio` output

A `variant_visit.cpp` compile looks like this near the top of the report:

```text
100.00%   1.75%  clang++ compilation
          |--91.64%--clang frontend
          |          template instantiation [8]
          |          |--8.64%--VariantDispatcher<...>::run
          |          |           --7.94%--std::visit<Overloaded<...>, const std::variant<...>&>
```

A heavier metaprogramming example produces a deep instantiation chain:

```text
100.00%   2.99%  clang++ compilation
          |--95.83%--clang frontend
          |          |--69.64%--template instantiation
          |          |          |--48.81%--ValueAt<100, ValueList<...>>
          |          |          |           --48.21%--ValueAt<99, ValueList<...>>
```

### Example caller and callee views

Caller view keeps the expansion direction visible:

```text
template instantiation [8]
VariantDispatcher<std::variant<...>>::run
std::visit<Overloaded<...>, const std::variant<...>&>
```

Callee view shows the same frames from the other direction:

```text
ValueAt<100, ValueList<...>>
template instantiation
clang frontend
clang++ compilation
```

### Example `perf script` output

`perf script` shows the synthetic stack samples in timestamp order:

```text
1000001f0 clang++ compilation+0x0 (synthetic-image.so)
100000200 clang frontend+0x0 (synthetic-image.so)
100000210 template instantiation+0x0 (synthetic-image.so)
100000220 ValueAt<100, ValueList<...>>+0x0 (synthetic-image.so)
```

## Troubleshooting

- make sure `perf` is installed and runnable for your user
- make sure `nm` is installed; the tool uses it to map synthetic symbols into the generated shared object
- make sure the synthetic ELF stays on disk next to the generated profile data
- if symbol resolution looks wrong, re-run with `--emit-intermediate` and inspect the output directory
- the direct writer fails fast on non-Linux, non-`x86_64`, or non-little-endian hosts
