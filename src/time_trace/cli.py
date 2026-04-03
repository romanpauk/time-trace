from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import PipelineOptions, probe_trace_file, run_pipeline, run_trace_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="time-trace",
        description="Wrap clang/clang++ with -ftime-trace and emit perf-friendly artifacts.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Directory for generated artifacts (defaults to time-trace-out/<stem>-<timestamp>).",
    )
    parser.add_argument(
        "--trace-file",
        type=Path,
        help="Use an existing clang time-trace JSON file instead of running clang.",
    )
    parser.add_argument(
        "--compiler",
        default="clang",
        help="Compiler used to build the synthetic symbol image when --trace-file is used.",
    )
    parser.add_argument(
        "--keep-trace",
        action="store_true",
        help="Copy the raw clang time-trace JSON into the output directory.",
    )
    parser.add_argument(
        "--emit-intermediate",
        action="store_true",
        help="Keep synthetic LLVM IR alongside the final perf artifacts.",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        help=(
            "Maximum number of reconstructed call-tree nodes to retain; "
            "omitted keeps the full tree."
        ),
    )
    parser.add_argument(
        "--sample-frequency",
        type=int,
        help="Synthetic sampling frequency in Hz used when writing perf.data directly.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="PATTERN",
        help=(
            "Keep only matching clang time-trace events. Patterns can be repeated and use "
            "glob syntax. Prefix with name:, label:, tag:, or cat: to match a specific field."
        ),
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help=(
            "Drop matching clang time-trace events after includes are applied. Patterns can "
            "be repeated and use glob syntax with name:, label:, tag:, or cat:."
        ),
    )
    parser.add_argument(
        "--list-event-names",
        action="store_true",
        help="List unique raw clang event names from --trace-file after include/exclude filters.",
    )
    parser.add_argument(
        "--list-tags",
        action="store_true",
        help="List derived event tags from --trace-file after include/exclude filters.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print generated artifact paths after a successful run.",
    )
    parser.add_argument(
        "compiler_argv",
        nargs=argparse.REMAINDER,
        help="Compiler invocation beginning with clang or clang++.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        options = PipelineOptions(
            output_dir=args.output,
            keep_trace=args.keep_trace,
            emit_intermediate=args.emit_intermediate,
            max_nodes=args.max_nodes,
            sample_frequency=args.sample_frequency,
            include_patterns=tuple(args.include),
            exclude_patterns=tuple(args.exclude),
        )
        if args.list_event_names or args.list_tags:
            if args.trace_file is None:
                parser.error("--list-event-names/--list-tags require --trace-file")
            if _normalize_compiler_argv(args.compiler_argv):
                parser.error("do not pass a compiler command when listing events from --trace-file")
            names, tags = probe_trace_file(args.trace_file, options=options)
            if args.list_event_names:
                for name in names:
                    print(name)
            if args.list_event_names and args.list_tags:
                print()
            if args.list_tags:
                for tag in tags:
                    print(tag)
            return 0
        if args.trace_file is not None:
            if _normalize_compiler_argv(args.compiler_argv):
                parser.error("do not pass a compiler command when --trace-file is used")
            result = run_trace_file(args.trace_file, options=options, compiler=args.compiler)
        else:
            compiler_argv = _normalize_compiler_argv(args.compiler_argv)
            if not compiler_argv:
                parser.error("expected a compiler command after time-trace options")
            result = run_pipeline(compiler_argv, options=options)
    except Exception as exc:  # pragma: no cover - exercised via integration/runtime use
        print(f"time-trace: {exc}", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"trace json: {result.trace_path}")
        print(f"perf data: {result.perf_artifacts.perf_data_path}")
        print(f"synthetic elf: {result.perf_artifacts.synthetic_image_path}")
        print(f"output dir: {result.output_dir}")
    else:
        print(result.perf_artifacts.perf_data_path)
    return 0


def _normalize_compiler_argv(argv: list[str]) -> list[str]:
    if argv and argv[0] == "--":
        return argv[1:]
    return argv


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
