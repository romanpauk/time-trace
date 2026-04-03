from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from time_trace.perf_writer import _ensure_supported_host, emit_perf_profile
from time_trace.trace_model import PlannedSample, SamplingPlan, SymbolDefinition

pytestmark = pytest.mark.skipif(
    shutil.which("clang") is None or shutil.which("perf") is None or shutil.which("nm") is None,
    reason="clang, nm, and perf are required for the direct-writer smoke test",
)


def test_emit_perf_profile_generates_perf_report_and_script(tmp_path: Path) -> None:
    plan = SamplingPlan(
        root_symbol_name="clang frontend",
        total_duration_us=1_000,
        sample_count=32,
        symbols=(
            SymbolDefinition(symbol_name="clang frontend", display_label="clang frontend"),
            SymbolDefinition(symbol_name="tmpl::leaf<int>", display_label="tmpl::leaf<int>"),
        ),
        samples=tuple(
            PlannedSample(
                timestamp_ns=index + 1,
                period=1,
                stack_symbols=("tmpl::leaf<int>", "clang frontend"),
            )
            for index in range(32)
        ),
    )

    artifacts = emit_perf_profile(
        plan,
        output_dir=tmp_path,
        compiler="clang",
        keep_intermediate=True,
    )

    assert artifacts.perf_data_path.exists()
    assert artifacts.synthetic_image_path.exists()
    report = artifacts.report_path.read_text()
    assert "clang frontend" in report
    assert "tmpl::leaf<int>" in report
    assert "tmpl::leaf<int>" in artifacts.caller_report_path.read_text()
    assert "tmpl::leaf<int>" in artifacts.callee_report_path.read_text()
    script = artifacts.script_path.read_text()
    assert "tmpl::leaf<int>" in script


def test_ensure_supported_host_rejects_non_x86() -> None:
    with pytest.raises(RuntimeError, match="x86_64"):
        _ensure_supported_host(platform_name="linux", machine="aarch64", byteorder="little")
