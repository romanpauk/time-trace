from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

from time_trace.pipeline import PipelineResult, run_profile
from time_trace.trace_model import ProfileRequest

from .cpp_expectations import CppSampleCase

ROOT_DIR = Path(__file__).resolve().parents[2]
HOST_SUPPORTS_DIRECT_PERF = (
    shutil.which("clang++") is not None
    and shutil.which("perf") is not None
    and shutil.which("nm") is not None
    and sys.platform == "linux"
    and platform.machine() == "x86_64"
    and sys.byteorder == "little"
)
HOST_SUPPORTS_DIRECT_PERF_REASON = (
    "requires clang++, nm, perf, Linux, and a little-endian x86_64 host"
)


def sample_path(case: CppSampleCase) -> Path:
    return ROOT_DIR / case.source_path


def run_cpp_sample(case: CppSampleCase, tmp_path: Path) -> PipelineResult:
    source_path = sample_path(case)
    object_path = tmp_path / f"{source_path.stem}.o"
    return run_profile(
        ProfileRequest(
            compiler_argv=[
                "clang++",
                f"-std={case.language_standard}",
                *case.extra_args,
                "-c",
                str(source_path),
                "-o",
                str(object_path),
            ],
            output_dir=tmp_path / f"{source_path.stem}-artifacts",
            keep_trace=True,
            emit_intermediate=True,
            sample_frequency=4_000,
        )
    )


def read_perf_report(perf_data_path: Path, *, call_graph_order: str | None = None) -> str:
    command = ["perf", "report", "--stdio", "-i", str(perf_data_path), "--sort", "symbol"]
    if call_graph_order is not None:
        command.extend(["--call-graph", call_graph_order])
    return _run(command)


def read_perf_script(perf_data_path: Path) -> str:
    return _run(["perf", "script", "-i", str(perf_data_path)])


def assert_contains_any(text: str, fragments: tuple[str, ...], *, context: str) -> None:
    if any(fragment in text for fragment in fragments):
        return
    joined = ", ".join(repr(fragment) for fragment in fragments)
    raise AssertionError(f"expected {context} to contain one of: {joined}")


def assert_contains_groups(text: str, groups: tuple[tuple[str, ...], ...], *, context: str) -> None:
    for group in groups:
        assert_contains_any(text, group, context=context)


def assert_contains_ordered_chain(text: str, chain: tuple[str, ...], *, context: str) -> None:
    joined = " -> ".join(repr(item) for item in chain)
    for block in _call_graph_blocks(text):
        start_index = 0
        for fragment in chain:
            for index in range(start_index, len(block)):
                if fragment in block[index]:
                    start_index = index + 1
                    break
            else:
                break
        else:
            return
    raise AssertionError(
        f"expected {context} to contain ordered chain within one call-graph block: {joined}"
    )


def assert_contains_ordered_chains(
    text: str,
    chains: tuple[tuple[str, ...], ...],
    *,
    context: str,
) -> None:
    for chain in chains:
        assert_contains_ordered_chain(text, chain, context=context)


def _call_graph_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = []
            continue
        if stripped.startswith("#"):
            continue
        if stripped in {"|", "---", "--"}:
            continue
        current.append(stripped)
    if current:
        blocks.append(current)
    return blocks


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() if completed.stderr else ""
        raise AssertionError(f"command failed: {' '.join(command)}\n{stderr}".strip())
    return completed.stdout
