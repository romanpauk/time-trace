from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .trace_model import ReplayNode


@dataclass(frozen=True)
class PerfArtifacts:
    perf_data_path: Path
    report_path: Path
    replay_ir_path: Path
    replay_binary_path: Path


def emit_perf_profile(
    root: ReplayNode,
    *,
    output_dir: Path,
    compiler: str = "clang",
    perf_binary: str = "perf",
    keep_intermediate: bool = False,
    sample_frequency: int | None = None,
) -> PerfArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    replay_ir_path = output_dir / "replay.ll"
    replay_binary_path = output_dir / "replay-helper"
    perf_data_path = output_dir / "perf.data"
    report_path = output_dir / "perf-report.txt"

    replay_ir_path.write_text(render_replay_ir(root))

    _run(
        [
            compiler,
            "-g",
            "-O0",
            "-fno-omit-frame-pointer",
            "-no-pie",
            str(replay_ir_path),
            "-o",
            str(replay_binary_path),
        ],
        context="compile replay helper",
    )
    _run(
        _build_perf_record_command(
            perf_binary=perf_binary,
            perf_data_path=perf_data_path,
            replay_binary_path=replay_binary_path,
            sample_frequency=sample_frequency,
        ),
        context="record synthetic perf profile",
    )

    report = smoke_report(perf_data_path, perf_binary=perf_binary)
    report_path.write_text(report)

    if not keep_intermediate:
        replay_ir_path.unlink(missing_ok=True)
        replay_binary_path.unlink(missing_ok=True)

    return PerfArtifacts(
        perf_data_path=perf_data_path,
        report_path=report_path,
        replay_ir_path=replay_ir_path,
        replay_binary_path=replay_binary_path,
    )


def smoke_report(perf_data_path: Path, *, perf_binary: str = "perf") -> str:
    completed = _run(
        [perf_binary, "report", "--stdio", "-i", str(perf_data_path), "--sort", "symbol"],
        context="validate perf report",
        capture_output=True,
    )
    return completed.stdout


def _build_perf_record_command(
    *,
    perf_binary: str,
    perf_data_path: Path,
    replay_binary_path: Path,
    sample_frequency: int | None,
) -> list[str]:
    command = [
        perf_binary,
        "record",
        "-q",
        "-g",
        "--call-graph",
        "dwarf",
        "-o",
        str(perf_data_path),
    ]
    if sample_frequency is not None:
        if sample_frequency <= 0:
            raise ValueError("sample_frequency must be positive when provided")
        command.extend(["-F", str(sample_frequency)])
    command.extend(["--", str(replay_binary_path)])
    return command


def render_replay_ir(root: ReplayNode) -> str:
    lines = ['source_filename = "time-trace-replay"', ""]
    lines.append("define i32 @main() #0 {")
    lines.append("entry:")
    lines.append(f"  call void @{_llvm_name(root.symbol_name)}()")
    lines.append("  ret i32 0")
    lines.append("}")
    lines.append("")

    for node in _walk_preorder(root):
        lines.extend(_render_function(node))
        lines.append("")

    lines.append('attributes #0 = { noinline nounwind optnone "frame-pointer"="all" }')
    lines.append("")
    return "\n".join(lines)


def _render_function(node: ReplayNode) -> list[str]:
    lines = [f"define void @{_llvm_name(node.symbol_name)}() #0 {{", "entry:"]
    for child in node.children:
        lines.append(f"  call void @{_llvm_name(child.symbol_name)}()")

    if node.self_iterations > 0:
        lines.extend(
            [
                "  br label %loop",
                "loop:",
                f"  %i = phi i64 [ {node.self_iterations}, %entry ], [ %next, %loop ]",
                "  %next = add nsw i64 %i, -1",
                "  %done = icmp eq i64 %next, 0",
                "  br i1 %done, label %exit, label %loop",
                "exit:",
                "  ret void",
            ]
        )
    else:
        lines.append("  ret void")

    lines.append("}")
    return lines


def _walk_preorder(root: ReplayNode) -> list[ReplayNode]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_walk_preorder(child))
    return nodes


def _llvm_name(symbol_name: str) -> str:
    escaped: list[str] = []
    for char in symbol_name:
        code_point = ord(char)
        if char in {'"', "\\"} or code_point < 0x20 or code_point > 0x7E:
            escaped.append(f"\\{code_point:02X}")
        else:
            escaped.append(char)
    return '"' + "".join(escaped) + '"'


def _run(
    command: list[str],
    *,
    context: str,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=capture_output,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() if completed.stderr else ""
        raise RuntimeError(f"failed to {context}: {' '.join(command)}\n{stderr}".strip())
    return completed
