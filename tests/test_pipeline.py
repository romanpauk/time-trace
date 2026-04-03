from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path

import pytest

from tests.support.perf_checks import read_perf_report, read_perf_script
from time_trace.perf_writer import PerfArtifacts
from time_trace.pipeline import PipelineOptions, probe_trace_file, run_pipeline, run_trace_file
from time_trace.trace_model import ProfileRequest

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


def test_pipeline_options_default_patterns_empty() -> None:
    assert PipelineOptions().include_patterns == ()
    assert PipelineOptions().exclude_patterns == ()
    assert ProfileRequest(["clang++"]).include_patterns == ()
    assert ProfileRequest(["clang++"]).exclude_patterns == ()


def test_pipeline_options_normalize_patterns_to_tuple() -> None:
    assert PipelineOptions(include_patterns=["tag:template"]).include_patterns == ("tag:template",)
    assert PipelineOptions(exclude_patterns=["tag:codegen"]).exclude_patterns == ("tag:codegen",)
    assert ProfileRequest(["clang++"], include_patterns=["name:Instantiate*"]).include_patterns == (
        "name:Instantiate*",
    )


def test_pipeline_options_reject_zero_sample_frequency() -> None:
    with pytest.raises(ValueError, match="positive"):
        PipelineOptions(sample_frequency=0)


def test_pipeline_options_reject_zero_max_nodes() -> None:
    with pytest.raises(ValueError, match="positive"):
        PipelineOptions(max_nodes=0)


def test_profile_request_rejects_zero_sample_frequency() -> None:
    with pytest.raises(ValueError, match="positive"):
        ProfileRequest(["clang++"], sample_frequency=0)


def test_profile_request_rejects_zero_max_nodes() -> None:
    with pytest.raises(ValueError, match="positive"):
        ProfileRequest(["clang++"], max_nodes=0)


def test_pipeline_options_reject_empty_include_pattern() -> None:
    with pytest.raises(ValueError, match="must not contain empty"):
        PipelineOptions(include_patterns=("",))


def test_profile_request_reject_empty_exclude_pattern() -> None:
    with pytest.raises(ValueError, match="must not contain empty"):
        ProfileRequest(["clang++"], exclude_patterns=("",))


def test_pipeline_options_reject_unsupported_filter_scope() -> None:
    with pytest.raises(ValueError, match="unsupported scope"):
        PipelineOptions(include_patterns=("phase:template",))


def test_profile_request_reject_unsupported_filter_scope() -> None:
    with pytest.raises(ValueError, match="unsupported scope"):
        ProfileRequest(["clang++"], exclude_patterns=("phase:template",))


def test_run_trace_file_uses_existing_json_and_does_not_copy_same_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "sample.json"
    trace_path.write_text("{}")
    perf_artifacts = PerfArtifacts(
        perf_data_path=tmp_path / "perf.data",
        synthetic_image_path=tmp_path / "synthetic-image.so",
        intermediate_ir_path=tmp_path / "synthetic-image.ll",
    )
    captured: dict[str, object] = {}

    def fake_build_perf_artifacts(
        *,
        trace_path: Path,
        output_dir: Path,
        options: object,
        compiler: str,
    ) -> PerfArtifacts:
        captured["trace_path"] = trace_path
        captured["output_dir"] = output_dir
        captured["options"] = options
        captured["compiler"] = compiler
        return perf_artifacts

    monkeypatch.setattr("time_trace.pipeline._build_perf_artifacts", fake_build_perf_artifacts)

    result = run_trace_file(
        trace_path,
        options=PipelineOptions(
            output_dir=tmp_path,
            keep_trace=True,
            include_patterns=("tag:frontend",),
        ),
        compiler="clang++",
    )

    assert result.wrapped_command is None
    assert result.trace_path == trace_path.resolve()
    assert captured["trace_path"] == trace_path.resolve()
    assert captured["output_dir"] == tmp_path
    assert captured["compiler"] == "clang++"
    assert result.perf_artifacts == perf_artifacts


def test_probe_trace_file_lists_filtered_names_and_tags(tmp_path: Path) -> None:
    trace_path = tmp_path / "sample.json"
    trace_path.write_text(
        """{
  "traceEvents": [
    {"ph": "X", "name": "InstantiateClass", "ts": 0, "dur": 5, "args": {"detail": "Foo<int>"}},
    {"ph": "X", "name": "RunPass", "ts": 5, "dur": 5, "args": {"detail": "PassManager<Function>"}}
  ]
}"""
    )

    names, tags = probe_trace_file(
        trace_path,
        options=PipelineOptions(include_patterns=("tag:template",)),
    )

    assert names == ("InstantiateClass",)
    assert "template" in tags
