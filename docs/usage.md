# Usage

## Basic invocation

```bash
time-trace clang++ -std=c++20 -c sample.cpp -o sample.o
```

The command:

1. adds `-ftime-trace`
2. runs clang
3. reconstructs a compiler call tree
4. writes `perf.data` and a synthetic symbol image

By default the tool prints the path to the generated `perf.data` file.

## Useful options

- `--output <dir>` — choose an output directory
- `--keep-trace` — copy the raw clang trace into the output directory
- `--emit-intermediate` — keep the synthetic LLVM IR that backs the symbol file
- `--max-nodes <n>` — limit the reconstructed tree size before sampling
- `--sample-frequency <hz>` — synthetic sampling frequency used when writing `perf.data`
- `--verbose` — print the main artifact paths

## Generated artifacts

A normal run writes:

- `perf.data`
- `synthetic-image.so`

With `--keep-trace`, it also keeps:

- raw clang time-trace JSON

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

## Useful perf workflows

Assuming you generated a profile like this from the repository root:

```bash
uv run time-trace --output .time-trace-example -- clang++ -std=c++20 -c tests/cpp_samples/variant_visit.cpp -o variant_visit.o
```

### Find the hottest template symbols

Show individual templates by inclusive and self samples:

```bash
perf report --stdio -i .time-trace-example/perf.data --sort symbol --fields overhead_children,overhead,symbol
```

This is the quickest way to answer “which instantiations cost the most overall?”

Example output:

```text
Children   Self  Symbol
16.40%     0.54% template instantiation [8]
 8.64%     0.27% VariantDispatcher<std::variant<...>>::run
 7.94%     0.67% std::visit<Overloaded<...>, const std::variant<...>&>
```

### Follow a hot template back to its callers

Use caller view to see what path in the compiler led to a hot template or helper:

```bash
perf report --stdio --call-graph caller -i .time-trace-example/perf.data --sort symbol
```

This is useful when a hot symbol like `std::visit` or `ValueAt<...>` is only the end of a larger instantiation chain.

Example output:

```text
clang frontend
template instantiation [8]
VariantDispatcher<std::variant<...>>::run
std::visit<Overloaded<...>, const std::variant<...>&>
```

### See what a hot wrapper expands into

Use callee view to walk downward into nested instantiations:

```bash
perf report --stdio --call-graph callee -i .time-trace-example/perf.data --sort symbol
```

This is useful for wrapper templates, visitors, constrained helpers, and type-list utilities.

Example output:

```text
ValueAt<100, ValueList<...>>
template instantiation
clang frontend
clang++ compilation
```

### Focus on self time instead of inclusive time

If you want templates with the most exclusive samples first, put self time first in the displayed fields:

```bash
perf report --stdio -i .time-trace-example/perf.data --sort symbol --fields overhead,overhead_children,symbol
```

This helps separate templates that are expensive themselves from templates that are only expensive because of their children.

Example output:

```text
Self      Children   Symbol
0.67%       7.94%    std::visit<Overloaded<...>, const std::variant<...>&>
0.54%      16.40%    template instantiation [8]
0.27%       8.64%    VariantDispatcher<std::variant<...>>::run
```

### Inspect the synthetic sample stream directly

Dump the reconstructed stacks in timestamp order:

```bash
perf script -i .time-trace-example/perf.data
```

This is useful for grepping symbols, diffing two runs, or building custom summaries on top of the synthetic samples.

Example output:

```text
1000001f0 clang++ compilation+0x0 (synthetic-image.so)
100000200 clang frontend+0x0 (synthetic-image.so)
100000210 template instantiation+0x0 (synthetic-image.so)
100000220 VariantDispatcher<std::variant<...>>::run+0x0 (synthetic-image.so)
```

### Compare two template-heavy implementations

Generate two profiles into separate directories, then inspect them side by side:

```bash
uv run time-trace --output .time-trace-variant -- clang++ -std=c++20 -c tests/cpp_samples/variant_visit.cpp -o variant_visit.o
uv run time-trace --output .time-trace-tuple -- clang++ -std=c++20 -c tests/cpp_samples/tuple_meta.cpp -o tuple_meta.o
perf report --stdio -i .time-trace-variant/perf.data --sort symbol --fields overhead_children,overhead,symbol
perf report --stdio -i .time-trace-tuple/perf.data --sort symbol --fields overhead_children,overhead,symbol
```

This is a good way to compare different APIs, metaprogramming styles, or library choices for compile-time cost.

Example comparison:

```text
variant_visit: template instantiation [8]                   16.40% children
tuple_meta:    ValueAt<100, ValueList<...>>                 48.81% children
```

## Troubleshooting

- make sure `perf` is installed and runnable for your user
- make sure `nm` is installed; the tool uses it to map synthetic symbols into the generated shared object
- make sure the synthetic ELF stays on disk next to the generated profile data
- if symbol resolution looks wrong, re-run with `--emit-intermediate` and inspect the output directory
- the tool fails fast on non-Linux, non-`x86_64`, or non-little-endian hosts
