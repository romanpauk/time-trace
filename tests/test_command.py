from pathlib import Path

from time_trace.command import derive_trace_path, wrap_compile_command


def test_wrap_compile_command_adds_time_trace_once() -> None:
    wrapped = wrap_compile_command(["clang++", "-std=c++20", "-c", "sample.cpp", "-o", "sample.o"])
    assert wrapped.trace_path == Path("sample.json")
    assert wrapped.wrapped.count("-ftime-trace") == 1


def test_wrap_compile_command_preserves_existing_time_trace_flag() -> None:
    wrapped = wrap_compile_command(["clang++", "-c", "sample.cpp", "-ftime-trace"])
    assert wrapped.wrapped.count("-ftime-trace") == 1


def test_derive_trace_path_uses_source_when_output_missing() -> None:
    trace_path = derive_trace_path(["clang++", "-c", "dir/sample.cpp"])
    assert trace_path == Path("dir/sample.json")
