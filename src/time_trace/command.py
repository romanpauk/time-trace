from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cp",
    ".cpp",
    ".cxx",
    ".c++",
    ".C",
    ".CPP",
    ".ii",
    ".i",
    ".ixx",
    ".cppm",
}


@dataclass(frozen=True)
class WrappedCommand:
    original: tuple[str, ...]
    wrapped: tuple[str, ...]
    trace_path: Path
    output_path: Path | None
    source_path: Path | None


def wrap_compile_command(command: list[str]) -> WrappedCommand:
    if not command:
        raise ValueError("expected a direct clang command")

    compiler = Path(command[0]).name
    if not compiler.startswith("clang"):
        raise ValueError(f"unsupported compiler {command[0]!r}; expected clang/clang++")

    output_path = _find_output_path(command)
    source_path = _find_source_path(command)
    trace_path = derive_trace_path(command)

    wrapped = list(command)
    if "-ftime-trace" not in wrapped:
        wrapped.append("-ftime-trace")

    return WrappedCommand(
        original=tuple(command),
        wrapped=tuple(wrapped),
        trace_path=trace_path,
        output_path=output_path,
        source_path=source_path,
    )


def derive_trace_path(command: list[str]) -> Path:
    output_path = _find_output_path(command)
    if output_path is not None:
        return output_path.with_suffix(".json")

    source_path = _find_source_path(command)
    if source_path is None:
        raise ValueError("could not infer the clang time-trace JSON path from the command")
    return source_path.with_suffix(".json")


def _find_output_path(command: list[str]) -> Path | None:
    for index, arg in enumerate(command):
        if arg == "-o" and index + 1 < len(command):
            return Path(command[index + 1])
        if arg.startswith("-o") and arg != "-o":
            return Path(arg[2:])
    return None


def _find_source_path(command: list[str]) -> Path | None:
    for arg in command[1:]:
        if arg.startswith("-"):
            continue
        if Path(arg).suffix in _SOURCE_SUFFIXES:
            return Path(arg)
    return None
