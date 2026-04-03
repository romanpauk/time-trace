from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.support.perf_checks import read_perf_report, read_perf_script
from time_trace.perf_writer import _ensure_supported_host, emit_perf_profile
from time_trace.trace_model import PlannedSample, SamplingPlan, SymbolDefinition

pytestmark = pytest.mark.skipif(
    shutil.which("clang") is None or shutil.which("perf") is None or shutil.which("nm") is None,
    reason="clang, nm, and perf are required for the direct-writer smoke test",
)


def test_emit_perf_profile_generates_perf_compatible_output(tmp_path: Path) -> None:
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
    report = read_perf_report(artifacts.perf_data_path)
    assert "clang frontend" in report
    assert "tmpl::leaf<int>" in report
    caller_report = read_perf_report(artifacts.perf_data_path, call_graph_order="caller")
    callee_report = read_perf_report(artifacts.perf_data_path, call_graph_order="callee")
    assert "tmpl::leaf<int>" in caller_report
    assert "tmpl::leaf<int>" in callee_report
    script = read_perf_script(artifacts.perf_data_path)
    assert "tmpl::leaf<int>" in script


def test_emit_perf_profile_writes_all_expected_artifacts(tmp_path: Path) -> None:
    plan = SamplingPlan(
        root_symbol_name="clang frontend",
        total_duration_us=1_000,
        sample_count=8,
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
            for index in range(8)
        ),
    )

    artifacts = emit_perf_profile(
        plan,
        output_dir=tmp_path,
        compiler="clang",
    )

    assert artifacts.perf_data_path.exists()
    assert artifacts.synthetic_image_path.exists()


def test_ensure_supported_host_rejects_non_x86() -> None:
    with pytest.raises(RuntimeError, match="x86_64"):
        _ensure_supported_host(platform_name="linux", machine="aarch64", byteorder="little")
