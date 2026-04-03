from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path

import pytest

from tests.support.perf_checks import read_perf_report, read_perf_script
from time_trace.pipeline import PipelineOptions, run_pipeline

pytestmark = pytest.mark.skipif(
    shutil.which("clang++") is None
    or shutil.which("perf") is None
    or shutil.which("nm") is None
    or platform.machine() != "x86_64"
    or sys.byteorder != "little",
    reason="clang++, nm, perf, and a little-endian x86_64 host are required",
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
            sample_frequency=4_000,
        ),
    )

    assert result.perf_artifacts.perf_data_path.exists()
    assert result.perf_artifacts.synthetic_image_path.exists()
    report = read_perf_report(result.perf_artifacts.perf_data_path)
    assert "clang frontend" in report or "codegen" in report
    assert any(path.suffix == ".json" for path in output.iterdir())


def test_run_pipeline_writes_all_expected_artifacts(tmp_path: Path) -> None:
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
            emit_intermediate=False,
            max_nodes=64,
            sample_frequency=4_000,
        ),
    )

    assert result.perf_artifacts.perf_data_path.exists()
    assert "clang frontend" in read_perf_report(result.perf_artifacts.perf_data_path)
    assert read_perf_script(result.perf_artifacts.perf_data_path)
