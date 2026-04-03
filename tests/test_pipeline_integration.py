from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.cpp_expectations import CppSampleCase
from tests.support.perf_checks import (
    HOST_SUPPORTS_DIRECT_PERF,
    HOST_SUPPORTS_DIRECT_PERF_REASON,
    assert_contains_groups,
    assert_contains_ordered_chains,
    read_perf_report,
    read_perf_script,
    run_cpp_sample,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not HOST_SUPPORTS_DIRECT_PERF, reason=HOST_SUPPORTS_DIRECT_PERF_REASON),
]


TINY_TUPLE_CASE = CppSampleCase(
    name="tiny-tuple",
    source_name="tiny_tuple.cpp",
    report_groups=(("clang frontend",), ("template", "TinyWrap", "TinyTuple")),
    script_groups=(("clang frontend", "template", "TinyWrap", "TinyTuple"),),
    caller_groups=(("clang frontend",),),
    callee_groups=(("clang frontend", "template"),),
    caller_chains=(),
    callee_chains=(("template", "clang frontend", "clang++ compilation"),),
)


def test_pipeline_generates_perf_report_for_tiny_compile(tmp_path: Path) -> None:
    result = run_cpp_sample(TINY_TUPLE_CASE, tmp_path)

    assert result.perf_data_path.exists()
    report_text = read_perf_report(result.perf_data_path)
    caller_text = read_perf_report(result.perf_data_path, call_graph_order="caller")
    callee_text = read_perf_report(result.perf_data_path, call_graph_order="callee")
    script_text = read_perf_script(result.perf_data_path)

    assert_contains_groups(report_text, TINY_TUPLE_CASE.report_groups, context="tiny report")
    assert_contains_groups(caller_text, TINY_TUPLE_CASE.caller_groups, context="tiny caller report")
    assert_contains_groups(callee_text, TINY_TUPLE_CASE.callee_groups, context="tiny callee report")
    assert_contains_groups(script_text, TINY_TUPLE_CASE.script_groups, context="tiny perf script")
    assert_contains_ordered_chains(
        callee_text,
        TINY_TUPLE_CASE.callee_chains,
        context="tiny callee report",
    )
    assert any(path.suffix == ".json" for path in result.output_dir.iterdir())
