from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from time_trace.cli import main
from time_trace.perf_writer import PerfArtifacts


def test_main_invokes_pipeline_and_prints_perf_data(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    perf_data_path = tmp_path / "perf.data"
    trace_path = tmp_path / "sample.json"
    captured: dict[str, object] = {}

    def fake_run_pipeline(command: list[str], *, options: object) -> object:
        captured["command"] = command
        captured["options"] = options
        return SimpleNamespace(
            trace_path=trace_path,
            output_dir=tmp_path,
            perf_artifacts=PerfArtifacts(
                perf_data_path=perf_data_path,
                synthetic_image_path=tmp_path / "synthetic-image.so",
                intermediate_ir_path=tmp_path / "synthetic-image.ll",
            ),
        )

    monkeypatch.setattr("time_trace.cli.run_pipeline", fake_run_pipeline)

    exit_code = main(["--keep-trace", "--", "clang++", "-c", "sample.cpp", "-o", "sample.o"])

    assert exit_code == 0
    assert captured["command"] == ["clang++", "-c", "sample.cpp", "-o", "sample.o"]
    assert capsys.readouterr().out.strip() == str(perf_data_path)


def test_main_invokes_pipeline_with_default_options(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    perf_data_path = tmp_path / "perf.data"
    captured: dict[str, object] = {}

    def fake_run_pipeline(command: list[str], *, options: object) -> object:
        captured["command"] = command
        captured["options"] = options
        return SimpleNamespace(
            trace_path=tmp_path / "sample.json",
            output_dir=tmp_path,
            perf_artifacts=PerfArtifacts(
                perf_data_path=perf_data_path,
                synthetic_image_path=tmp_path / "synthetic-image.so",
                intermediate_ir_path=tmp_path / "synthetic-image.ll",
            ),
        )

    monkeypatch.setattr("time_trace.cli.run_pipeline", fake_run_pipeline)

    exit_code = main(["--", "clang++", "-c", "sample.cpp", "-o", "sample.o"])

    assert exit_code == 0
    assert captured["command"] == ["clang++", "-c", "sample.cpp", "-o", "sample.o"]
    options = cast(SimpleNamespace, captured["options"])
    assert options is not None
    assert options.max_nodes is None
    assert options.include_patterns == ()
    assert options.exclude_patterns == ()
    assert capsys.readouterr().out.strip() == str(perf_data_path)


def test_main_requires_compiler_command() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code == 2


def test_main_can_use_existing_trace_file(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    perf_data_path = tmp_path / "perf.data"
    trace_path = tmp_path / "sample.json"
    captured: dict[str, object] = {}

    def fake_run_trace_file(trace_file: Path, *, options: object, compiler: str) -> object:
        captured["trace_file"] = trace_file
        captured["options"] = options
        captured["compiler"] = compiler
        return SimpleNamespace(
            trace_path=trace_path,
            output_dir=tmp_path,
            perf_artifacts=PerfArtifacts(
                perf_data_path=perf_data_path,
                synthetic_image_path=tmp_path / "synthetic-image.so",
                intermediate_ir_path=tmp_path / "synthetic-image.ll",
            ),
        )

    monkeypatch.setattr("time_trace.cli.run_trace_file", fake_run_trace_file)

    exit_code = main(["--trace-file", str(trace_path), "--compiler", "clang++"])

    assert exit_code == 0
    assert captured["trace_file"] == trace_path
    assert captured["compiler"] == "clang++"
    assert capsys.readouterr().out.strip() == str(perf_data_path)


def test_main_rejects_compiler_command_with_trace_file() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--trace-file", "sample.json", "--", "clang++", "-c", "sample.cpp"])

    assert excinfo.value.code == 2


def test_main_passes_filters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    perf_data_path = tmp_path / "perf.data"
    captured: dict[str, object] = {}

    def fake_run_pipeline(command: list[str], *, options: object) -> object:
        captured["command"] = command
        captured["options"] = options
        return SimpleNamespace(
            trace_path=tmp_path / "sample.json",
            output_dir=tmp_path,
            perf_artifacts=PerfArtifacts(
                perf_data_path=perf_data_path,
                synthetic_image_path=tmp_path / "synthetic-image.so",
                intermediate_ir_path=tmp_path / "synthetic-image.ll",
            ),
        )

    monkeypatch.setattr("time_trace.cli.run_pipeline", fake_run_pipeline)

    exit_code = main(
        [
            "--include",
            "tag:template",
            "--exclude",
            "label:*register_type*",
            "--",
            "clang++",
            "-c",
            "sample.cpp",
            "-o",
            "sample.o",
        ]
    )

    assert exit_code == 0
    options = cast(SimpleNamespace, captured["options"])
    assert options.include_patterns == ("tag:template",)
    assert options.exclude_patterns == ("label:*register_type*",)
    assert capsys.readouterr().out.strip() == str(perf_data_path)


def test_main_can_list_event_names_and_tags(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "sample.json"
    captured: dict[str, object] = {}

    def fake_probe_trace_file(
        trace_file: Path, *, options: object
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        captured["trace_file"] = trace_file
        captured["options"] = options
        return (("InstantiateClass", "RunPass"), ("backend", "codegen", "template"))

    monkeypatch.setattr("time_trace.cli.probe_trace_file", fake_probe_trace_file)

    exit_code = main(
        [
            "--trace-file",
            str(trace_path),
            "--include",
            "tag:template",
            "--list-event-names",
            "--list-tags",
        ]
    )

    assert exit_code == 0
    assert captured["trace_file"] == trace_path
    assert capsys.readouterr().out.strip() == "\n".join(
        ["InstantiateClass", "RunPass", "", "backend", "codegen", "template"]
    )


def test_main_rejects_listing_without_trace_file() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--list-tags"])

    assert excinfo.value.code == 2


def test_main_rejects_compiler_command_when_listing_trace_file() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--trace-file", "sample.json", "--list-tags", "--", "clang++", "-c", "sample.cpp"])

    assert excinfo.value.code == 2


def test_main_reports_unsupported_filter_scope(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        ["--include", "phase:template", "--", "clang++", "-c", "sample.cpp", "-o", "sample.o"]
    )

    assert exit_code == 1
    assert "unsupported scope" in capsys.readouterr().err
