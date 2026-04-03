from __future__ import annotations

import platform
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .elf_writer import emit_synthetic_elf
from .perf_data_model import PerfWriterContract, build_perf_file_layout
from .trace_model import PlannedSample, SamplingBlueprint


@dataclass(frozen=True)
class PerfArtifacts:
    perf_data_path: Path
    synthetic_image_path: Path
    intermediate_ir_path: Path


def emit_perf_profile(
    plan: SamplingBlueprint,
    *,
    output_dir: Path,
    compiler: str,
    keep_intermediate: bool = False,
    samples: Iterable[PlannedSample],
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

    allowed_symbols = {symbol.symbol_name for symbol in plan.symbols}
    written_count = 0

    def validated_samples() -> Iterable[PlannedSample]:
        nonlocal written_count
        for sample in samples:
            for symbol_name in sample.stack_symbols:
                if symbol_name not in allowed_symbols:
                    raise ValueError(
                        f"sample symbol {symbol_name!r} is not declared in the sampling blueprint"
                    )
            written_count += 1
            yield sample

    perf_data_path = output_dir / "perf.data"
    file_layout = build_perf_file_layout(
        contract,
        synthetic_elf=synthetic_elf,
        samples=validated_samples(),
    )
    if written_count != plan.sample_count:
        raise ValueError(
            f"sampling blueprint expected {plan.sample_count} samples, wrote {written_count}"
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
