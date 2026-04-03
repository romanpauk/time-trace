from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from time_trace.perf_writer import emit_perf_profile
from time_trace.trace_model import ReplayNode

pytestmark = pytest.mark.skipif(
    shutil.which("clang") is None or shutil.which("perf") is None,
    reason="clang and perf are required for the replay smoke test",
)


def test_emit_perf_profile_generates_perf_report(tmp_path: Path) -> None:
    root = ReplayNode(
        symbol_name="clang frontend",
        display_label="clang frontend",
        self_iterations=30_000_000,
        children=(
            ReplayNode(
                symbol_name="tmpl::leaf<int>",
                display_label="tmpl::leaf<int>",
                self_iterations=20_000_000,
            ),
        ),
    )

    artifacts = emit_perf_profile(root, output_dir=tmp_path, keep_intermediate=True)

    assert artifacts.perf_data_path.exists()
    report = artifacts.report_path.read_text()
    assert "clang frontend" in report
    assert "tmpl::leaf<int>" in report
