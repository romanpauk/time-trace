from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import PipelineOptions, run_pipeline


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
        "--keep-trace",
        action="store_true",
        help="Copy the raw clang time-trace JSON into the output directory.",
    )
    parser.add_argument(
        "--emit-intermediate",
        action="store_true",
        help="Keep replay helper inputs alongside the final perf artifacts.",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=512,
        help="Maximum number of reconstructed call-tree nodes to retain.",
    )
    parser.add_argument(
        "--target-iterations",
        type=int,
        default=120_000_000,
        help="Replay loop budget used to approximate relative self time.",
    )
    parser.add_argument(
        "--sample-frequency",
        type=int,
        help="Optional perf record sample frequency for the synthetic replay helper.",
    )
    parser.add_argument(
        "--replay-compiler",
        default="clang",
        help="Compiler used to build the synthetic replay helper.",
    )
    parser.add_argument(
        "--perf-binary",
        default="perf",
        help="perf executable used for record/report commands.",
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
    compiler_argv = _normalize_compiler_argv(args.compiler_argv)
    if not compiler_argv:
        parser.error("expected a compiler command after time-trace options")

    try:
        result = run_pipeline(
            compiler_argv,
            options=PipelineOptions(
                output_dir=args.output,
                keep_trace=args.keep_trace,
                emit_intermediate=args.emit_intermediate,
                max_nodes=args.max_nodes,
                target_iterations=args.target_iterations,
                sample_frequency=args.sample_frequency,
                replay_compiler=args.replay_compiler,
                perf_binary=args.perf_binary,
            ),
        )
    except Exception as exc:  # pragma: no cover - exercised via integration/runtime use
        print(f"time-trace: {exc}", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"trace json: {result.trace_path}")
        print(f"perf data: {result.perf_artifacts.perf_data_path}")
        print(f"report: {result.perf_artifacts.report_path}")
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
