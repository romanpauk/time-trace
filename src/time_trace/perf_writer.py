from __future__ import annotations

import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .elf_writer import emit_synthetic_elf
from .perf_data_model import PerfWriterContract, build_perf_file_layout
from .trace_model import SamplingPlan


@dataclass(frozen=True)
class PerfArtifacts:
    perf_data_path: Path
    report_path: Path
    caller_report_path: Path
    callee_report_path: Path
    script_path: Path
    synthetic_image_path: Path
    intermediate_ir_path: Path


def emit_perf_profile(
    plan: SamplingPlan,
    *,
    output_dir: Path,
    compiler: str,
    perf_binary: str = "perf",
    keep_intermediate: bool = False,
) -> PerfArtifacts:
    _ensure_supported_host()
    output_dir.mkdir(parents=True, exist_ok=True)
    contract = PerfWriterContract()
    synthetic_elf = emit_synthetic_elf(
        plan,
        output_dir=output_dir,
        compiler=compiler,
        base_address=contract.base_address,
        keep_intermediate=keep_intermediate,
    )

    perf_data_path = output_dir / "perf.data"
    report_path = output_dir / "perf-report.txt"
    caller_report_path = output_dir / "perf-report-caller.txt"
    callee_report_path = output_dir / "perf-report-callee.txt"
    script_path = output_dir / "perf-script.txt"

    file_layout = build_perf_file_layout(
        contract,
        synthetic_elf=synthetic_elf,
        samples=plan.samples,
    )
    perf_data_path.write_bytes(file_layout.file_bytes)

    report_path.write_text(smoke_report(perf_data_path, perf_binary=perf_binary))
    caller_report_path.write_text(
        smoke_report(
            perf_data_path,
            perf_binary=perf_binary,
            call_graph_order="caller",
        )
    )
    callee_report_path.write_text(
        smoke_report(
            perf_data_path,
            perf_binary=perf_binary,
            call_graph_order="callee",
        )
    )
    script_path.write_text(smoke_script(perf_data_path, perf_binary=perf_binary))

    return PerfArtifacts(
        perf_data_path=perf_data_path,
        report_path=report_path,
        caller_report_path=caller_report_path,
        callee_report_path=callee_report_path,
        script_path=script_path,
        synthetic_image_path=synthetic_elf.image_path,
        intermediate_ir_path=synthetic_elf.ir_path,
    )


def smoke_report(
    perf_data_path: Path,
    *,
    perf_binary: str = "perf",
    call_graph_order: str | None = None,
) -> str:
    command = [perf_binary, "report", "--stdio", "-i", str(perf_data_path), "--sort", "symbol"]
    if call_graph_order is not None:
        command.extend(["--call-graph", call_graph_order])
    completed = _run(command, context="validate perf report", capture_output=True)
    return completed.stdout


def smoke_script(perf_data_path: Path, *, perf_binary: str = "perf") -> str:
    completed = _run(
        [perf_binary, "script", "-i", str(perf_data_path)],
        context="validate perf script",
        capture_output=True,
    )
    return completed.stdout


def _ensure_supported_host(
    *,
    platform_name: str | None = None,
    machine: str | None = None,
    byteorder: str | None = None,
) -> None:
    resolved_platform = platform_name or sys.platform
    resolved_machine = machine or platform.machine()
    resolved_byteorder = byteorder or sys.byteorder

    if resolved_platform != "linux":
        raise RuntimeError("time-trace currently supports direct perf.data writing only on Linux")
    if resolved_machine != "x86_64":
        raise RuntimeError(
            "time-trace currently supports direct perf.data writing only on x86_64 hosts"
        )
    if resolved_byteorder != "little":
        raise RuntimeError(
            "time-trace currently supports direct perf.data writing only on little-endian hosts"
        )


def _run(
    command: list[str],
    *,
    context: str,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=capture_output,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() if completed.stderr else ""
        raise RuntimeError(f"failed to {context}: {' '.join(command)}\n{stderr}".strip())
    return completed
