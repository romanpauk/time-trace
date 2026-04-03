# Usage

## Basic invocation

```bash
time-trace clang++ -std=c++20 -c sample.cpp -o sample.o
```

Or start from an existing clang trace JSON:

```bash
time-trace --trace-file sample.json
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
- `--max-nodes <n>` — limit the reconstructed tree size before sampling; omitted keeps the full tree
- `--sample-frequency <hz>` — synthetic sampling frequency used when writing `perf.data`
- `--include <pattern>` — keep only matching trace events; repeat as needed. Patterns use glob syntax and can target `name:`, `label:`, `tag:`, or `cat:`
- `--exclude <pattern>` — drop matching trace events after includes are applied
- `--list-event-names` — print unique raw clang event names from `--trace-file` after filtering
- `--list-tags` — print derived event tags from `--trace-file` after filtering
- `--verbose` — print the main artifact paths

On the clang traces used here, `cat` is usually empty, so `name:` and `tag:` are the most useful selectors.

Derived tags are small and additive. Examples include:

- `template`
- `parse`
- `semantic`
- `overload`
- `resolution`
- `frontend`
- `codegen`
- `backend`

Examples:

```bash
time-trace --include tag:template -- clang++ -c sample.cpp -o sample.o
time-trace --include 'name:Instantiate*' --include 'label:*register_type*' -- clang++ -c sample.cpp -o sample.o
time-trace --trace-file sample.json --exclude tag:codegen
time-trace --trace-file sample.json --list-event-names
time-trace --trace-file sample.json --list-tags
```

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
perf report --stdio --percent-limit 0 --call-graph caller -i path/to/perf.data --sort symbol
perf report --stdio --percent-limit 0 --call-graph callee -i path/to/perf.data --sort symbol
perf script -i path/to/perf.data
```

### Example `perf report --stdio` output

A template-only `variant_visit.cpp` compile looks like this near the top of the report:

```text
clang++ compilation
`--template
   `--VariantDispatcher<std::variant<...>>::run
      `--std::visit<Overloaded<...>, const std::variant<...>&>
         `--std::__do_visit<...>
```

A heavier template-only metaprogramming example produces a deep template chain:

```text
clang++ compilation
`--template
   `--ValueAt<100, ValueList<...>>
      `--ValueAt<99, ValueList<...>>
         `--ValueAt<98, ValueList<...>>
```

### Example caller and callee views

Use `--percent-limit 0` for tree browsing so perf keeps very small descendants visible.

Caller view keeps the expansion direction visible:

```text
clang++ compilation
`--template
   `--VariantDispatcher<std::variant<...>>::run
      `--std::visit<Overloaded<...>, const std::variant<...>&>
```

Callee view shows the same frames from the other direction:

```text
ValueAt<100, ValueList<...>>
template
clang++ compilation
```

### Example `perf script` output

`perf script` shows the synthetic stack samples in timestamp order:

```text
1000001f0 clang++ compilation+0x0 (synthetic-image.so)
100000200 template+0x0 (synthetic-image.so)
100000210 ValueAt<100, ValueList<...>>+0x0 (synthetic-image.so)
100000220 ValueAt<99, ValueList<...>>+0x0 (synthetic-image.so)
```

## Useful perf workflows

Assuming you generated a profile like this from the repository root:

```bash
uv run time-trace --output .time-trace-example --include "tag:template" -- clang++ -std=c++20 -c tests/cpp_samples/variant_visit.cpp -o variant_visit.o
```

### Find the hottest template symbols

Show individual templates by inclusive and self samples:

```bash
perf report --stdio -i .time-trace-example/perf.data --sort symbol --fields overhead_children,overhead,symbol
```

This is the quickest way to answer “which templates cost the most overall?”

Example output:

```text
Children   Self  Symbol
17.35%     6.62% PerformPendingInstantiations
18.93%     0.63% VariantDispatcher<std::variant<...>>::run
17.67%     1.26% std::visit<Overloaded<...>, const std::variant<...>&>
```

### Follow a hot template back to its callers

Use caller view to see what path in the compiler led to a hot template or helper:

```bash
perf report --stdio --percent-limit 0 --call-graph caller -i .time-trace-example/perf.data --sort symbol
```

This is useful when a hot symbol like `std::visit` or `ValueAt<...>` is only the end of a larger template chain.

Example output:

```text
clang++ compilation
template
VariantDispatcher<std::variant<...>>::run
std::visit<Overloaded<...>, const std::variant<...>&>
```

### See what a hot wrapper expands into

Use callee view to walk downward into nested templates:

```bash
perf report --stdio --percent-limit 0 --call-graph callee -i .time-trace-example/perf.data --sort symbol
```

This is useful for wrapper templates, visitors, constrained helpers, and type-list utilities.

Example output:

```text
ValueAt<100, ValueList<...>>
template
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
6.62%      17.35%    PerformPendingInstantiations
1.26%      17.67%    std::visit<Overloaded<...>, const std::variant<...>&>
0.63%      18.93%    VariantDispatcher<std::variant<...>>::run
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
100000200 template+0x0 (synthetic-image.so)
100000210 VariantDispatcher<std::variant<...>>::run+0x0 (synthetic-image.so)
100000220 std::visit<Overloaded<...>, const std::variant<...>&>+0x0 (synthetic-image.so)
```

### Compare two template-heavy implementations

Generate two profiles into separate directories, then inspect them side by side:

```bash
uv run time-trace --output .time-trace-variant --include "tag:template" -- clang++ -std=c++20 -c tests/cpp_samples/variant_visit.cpp -o variant_visit.o
uv run time-trace --output .time-trace-tuple --include "tag:template" -- clang++ -std=c++20 -c tests/cpp_samples/tuple_meta.cpp -o tuple_meta.o
perf report --stdio -i .time-trace-variant/perf.data --sort symbol --fields overhead_children,overhead,symbol
perf report --stdio -i .time-trace-tuple/perf.data --sort symbol --fields overhead_children,overhead,symbol
```

This is a good way to compare different APIs, metaprogramming styles, or library choices for compile-time cost.

Example comparison:

```text
variant_visit: PerformPendingInstantiations               17.35% children
tuple_meta:    ValueAt<100, ValueList<...>>               70.43% children
```

## Troubleshooting

- make sure `perf` is installed and runnable for your user
- make sure `nm` is installed; the tool uses it to map synthetic symbols into the generated shared object
- make sure the synthetic ELF stays on disk next to the generated profile data
- if symbol resolution looks wrong, re-run with `--emit-intermediate` and inspect the output directory
- the tool fails fast on non-Linux, non-`x86_64`, or non-little-endian hosts
