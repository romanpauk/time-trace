from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .command import WrappedCommand, wrap_compile_command
from .perf_writer import PerfArtifacts, emit_perf_profile
from .reconstruct import build_call_tree, filter_events, list_event_names, list_event_tags
from .sampling import build_sampling_stream
from .trace_loader import load_trace
from .trace_model import (
    ProfileRequest,
    TraceEvent,
    _normalize_filter_patterns,
    _validate_filter_patterns,
    _validate_max_nodes,
    _validate_sample_frequency,
)


@dataclass(frozen=True)
class PipelineOptions:
    output_dir: Path | None = None
    keep_trace: bool = False
    emit_intermediate: bool = False
    max_nodes: int | None = None
    sample_frequency: int | None = None
    include_patterns: tuple[str, ...] | list[str] = ()
    exclude_patterns: tuple[str, ...] | list[str] = ()

    def __post_init__(self) -> None:
        normalized_include_patterns = _normalize_filter_patterns(self.include_patterns)
        normalized_exclude_patterns = _normalize_filter_patterns(self.exclude_patterns)
        object.__setattr__(self, "include_patterns", normalized_include_patterns)
        object.__setattr__(self, "exclude_patterns", normalized_exclude_patterns)
        _validate_max_nodes(self.max_nodes)
        _validate_sample_frequency(self.sample_frequency)
        _validate_filter_patterns(normalized_include_patterns, field_name="include_patterns")
        _validate_filter_patterns(normalized_exclude_patterns, field_name="exclude_patterns")


@dataclass(frozen=True)
class PipelineResult:
    wrapped_command: WrappedCommand | None
    trace_path: Path
    perf_artifacts: PerfArtifacts
    output_dir: Path

    @property
    def perf_data_path(self) -> Path:
        return self.perf_artifacts.perf_data_path


def run_pipeline(command: list[str], *, options: PipelineOptions) -> PipelineResult:
    wrapped = wrap_compile_command(command)
    output_dir = options.output_dir or _default_output_dir(wrapped)
    output_dir.mkdir(parents=True, exist_ok=True)

    _run_compile(wrapped)
    if not wrapped.trace_path.exists():
        raise RuntimeError(f"clang time trace not found at {wrapped.trace_path}")

    perf_artifacts = _build_perf_artifacts(
        trace_path=wrapped.trace_path,
        output_dir=output_dir,
        options=options,
        compiler=wrapped.original[0],
    )

    if options.keep_trace:
        _copy_trace_if_requested(wrapped.trace_path, output_dir)

    return PipelineResult(
        wrapped_command=wrapped,
        trace_path=wrapped.trace_path,
        perf_artifacts=perf_artifacts,
        output_dir=output_dir,
    )


def run_trace_file(
    trace_path: Path,
    *,
    options: PipelineOptions,
    compiler: str = "clang",
) -> PipelineResult:
    resolved_trace_path = trace_path.resolve()
    if not resolved_trace_path.exists():
        raise RuntimeError(f"clang time trace not found at {resolved_trace_path}")

    output_dir = options.output_dir or (Path.cwd() / "time-trace-out" / resolved_trace_path.stem)
    output_dir.mkdir(parents=True, exist_ok=True)

    perf_artifacts = _build_perf_artifacts(
        trace_path=resolved_trace_path,
        output_dir=output_dir,
        options=options,
        compiler=compiler,
    )

    if options.keep_trace:
        _copy_trace_if_requested(resolved_trace_path, output_dir)

    return PipelineResult(
        wrapped_command=None,
        trace_path=resolved_trace_path,
        perf_artifacts=perf_artifacts,
        output_dir=output_dir,
    )


def run_profile(request: ProfileRequest) -> PipelineResult:
    return run_pipeline(
        list(request.compiler_argv),
        options=PipelineOptions(
            output_dir=request.output_dir,
            keep_trace=request.keep_trace,
            emit_intermediate=request.emit_intermediate,
            max_nodes=request.max_nodes,
            sample_frequency=request.sample_frequency,
            include_patterns=request.include_patterns,
            exclude_patterns=request.exclude_patterns,
        ),
    )


def probe_trace_file(
    trace_path: Path, *, options: PipelineOptions
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    events = _load_selected_events(trace_path, options=options)
    return list_event_names(events), list_event_tags(events)


def _build_perf_artifacts(
    *,
    trace_path: Path,
    output_dir: Path,
    options: PipelineOptions,
    compiler: str,
) -> PerfArtifacts:
    events = _load_selected_events(trace_path, options=options)
    tree = build_call_tree(events, max_nodes=options.max_nodes)
    plan, samples = build_sampling_stream(
        tree,
        sample_frequency=options.sample_frequency,
    )
    return emit_perf_profile(
        plan,
        output_dir=output_dir,
        compiler=compiler,
        keep_intermediate=options.emit_intermediate,
        samples=samples,
    )


def _load_selected_events(trace_path: Path, *, options: PipelineOptions) -> list[TraceEvent]:
    return filter_events(
        load_trace(trace_path),
        include_patterns=tuple(options.include_patterns),
        exclude_patterns=tuple(options.exclude_patterns),
    )


def _copy_trace_if_requested(trace_path: Path, output_dir: Path) -> None:
    destination = output_dir / trace_path.name
    if destination.resolve() == trace_path.resolve():
        return
    shutil.copy2(trace_path, destination)


def _default_output_dir(wrapped: WrappedCommand) -> Path:
    base = wrapped.output_path or wrapped.source_path or Path("trace")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path.cwd() / "time-trace-out" / f"{base.stem}-{timestamp}"


def _run_compile(wrapped: WrappedCommand) -> None:
    completed = subprocess.run(
        list(wrapped.wrapped),
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() if completed.stderr else ""
        raise RuntimeError(f"clang command failed: {' '.join(wrapped.wrapped)}\n{stderr}".strip())
