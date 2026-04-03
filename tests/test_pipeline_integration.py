from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from time_trace.pipeline import run_profile
from time_trace.trace_model import ProfileRequest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    shutil.which("clang++") is None or shutil.which("perf") is None,
    reason="requires clang++ and perf",
)
def test_pipeline_generates_perf_report_for_tiny_compile(tmp_path: Path) -> None:
    source_path = tmp_path / "sample.cpp"
    source_path.write_text(
        """
        #include <tuple>
        template <typename T> struct Foo { using type = T; };
        template <typename... Ts>
        using Tup = std::tuple<typename Foo<Ts>::type...>;
        Tup<int, double, char> value;
        """
    )

    result = run_profile(
        ProfileRequest(
            compiler_argv=[
                "clang++",
                "-std=c++20",
                "-c",
                str(source_path),
                "-o",
                str(tmp_path / "sample.o"),
            ],
            output_dir=tmp_path / "artifacts",
            keep_trace=True,
            emit_intermediate=True,
            loop_budget=20_000_000,
            sample_frequency=4000,
        )
    )

    assert result.perf_data_path.exists()
    report_text = result.report_path.read_text()
    assert "clang frontend" in report_text
    assert "template instantiation" in report_text or "InstantiateClass" in report_text

    smoke = subprocess.run(
        ["perf", "report", "--stdio", "-i", str(result.perf_data_path), "--sort", "symbol"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert smoke.returncode == 0
    assert "clang frontend" in smoke.stdout
