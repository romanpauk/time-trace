from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .command import WrappedCommand, wrap_compile_command
from .perf_writer import PerfArtifacts, emit_perf_profile
from .reconstruct import build_call_tree
from .sampling import build_sampling_stream
from .trace_loader import load_trace
from .trace_model import ProfileRequest, _validate_sample_frequency


@dataclass(frozen=True)
class PipelineOptions:
    output_dir: Path | None = None
    keep_trace: bool = False
    emit_intermediate: bool = False
    max_nodes: int = 512
    sample_frequency: int | None = None

    def __post_init__(self) -> None:
        _validate_sample_frequency(self.sample_frequency)


@dataclass(frozen=True)
class PipelineResult:
    wrapped_command: WrappedCommand
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

    events = load_trace(wrapped.trace_path)
    tree = build_call_tree(events, max_nodes=options.max_nodes)
    plan, samples = build_sampling_stream(tree, sample_frequency=options.sample_frequency)
    perf_artifacts = emit_perf_profile(
        plan,
        output_dir=output_dir,
        compiler=wrapped.original[0],
        keep_intermediate=options.emit_intermediate,
        samples=samples,
    )

    if options.keep_trace:
        shutil.copy2(wrapped.trace_path, output_dir / wrapped.trace_path.name)

    return PipelineResult(
        wrapped_command=wrapped,
        trace_path=wrapped.trace_path,
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
        ),
    )


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
