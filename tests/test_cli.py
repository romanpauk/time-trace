from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from time_trace.cli import main
from time_trace.perf_writer import PerfArtifacts


def test_main_invokes_pipeline_and_prints_perf_data(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    perf_data_path = tmp_path / "perf.data"
    report_path = tmp_path / "perf-report.txt"
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
                report_path=report_path,
                caller_report_path=tmp_path / "perf-report-caller.txt",
                callee_report_path=tmp_path / "perf-report-callee.txt",
                script_path=tmp_path / "perf-script.txt",
                synthetic_image_path=tmp_path / "synthetic-image.so",
                intermediate_ir_path=tmp_path / "synthetic-image.ll",
            ),
        )

    monkeypatch.setattr("time_trace.cli.run_pipeline", fake_run_pipeline)

    exit_code = main(["--keep-trace", "--", "clang++", "-c", "sample.cpp", "-o", "sample.o"])

    assert exit_code == 0
    assert captured["command"] == ["clang++", "-c", "sample.cpp", "-o", "sample.o"]
    assert capsys.readouterr().out.strip() == str(perf_data_path)


def test_main_requires_compiler_command() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code == 2
