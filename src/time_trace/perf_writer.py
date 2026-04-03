from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from pathlib import Path

from .elf_writer import emit_synthetic_elf
from .perf_data_model import PerfWriterContract, build_perf_file_layout
from .trace_model import SamplingPlan


@dataclass(frozen=True)
class PerfArtifacts:
    perf_data_path: Path
    synthetic_image_path: Path
    intermediate_ir_path: Path


def emit_perf_profile(
    plan: SamplingPlan,
    *,
    output_dir: Path,
    compiler: str,
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
    file_layout = build_perf_file_layout(
        contract,
        synthetic_elf=synthetic_elf,
        samples=plan.samples,
    )
    perf_data_path.write_bytes(file_layout.file_bytes)

    return PerfArtifacts(
        perf_data_path=perf_data_path,
        synthetic_image_path=synthetic_elf.image_path,
        intermediate_ir_path=synthetic_elf.ir_path,
    )


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
