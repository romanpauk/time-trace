from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from time_trace.pipeline import PipelineOptions, run_pipeline

pytestmark = pytest.mark.skipif(
    shutil.which("clang++") is None or shutil.which("perf") is None,
    reason="clang++ and perf are required for the end-to-end pipeline test",
)


def test_run_pipeline_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "sample.cpp"
    source.write_text(
        """
#include <tuple>

template <typename T>
struct Wrap { using type = T; };

template <typename... Ts>
using Tup = std::tuple<typename Wrap<Ts>::type...>;

Tup<int, double, char> value;
""".strip()
    )
    output = tmp_path / "profile-out"

    result = run_pipeline(
        ["clang++", "-std=c++20", "-c", str(source), "-o", str(tmp_path / "sample.o")],
        options=PipelineOptions(
            output_dir=output,
            keep_trace=True,
            emit_intermediate=True,
            max_nodes=64,
            target_iterations=60_000_000,
        ),
    )

    assert result.perf_artifacts.perf_data_path.exists()
    report = result.perf_artifacts.report_path.read_text()
    assert "clang frontend" in report or "codegen" in report
    assert any(path.suffix == ".json" for path in output.iterdir())
