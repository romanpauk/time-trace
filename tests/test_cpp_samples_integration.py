from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.cpp_expectations import CPP_SAMPLE_CASES, CppSampleCase
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
    pytest.mark.perf_samples,
    pytest.mark.skipif(not HOST_SUPPORTS_DIRECT_PERF, reason=HOST_SUPPORTS_DIRECT_PERF_REASON),
]


@pytest.mark.parametrize("case", CPP_SAMPLE_CASES, ids=lambda case: case.name)
def test_pipeline_generates_usable_perf_outputs_for_cpp_samples(
    case: CppSampleCase,
    tmp_path: Path,
) -> None:
    result = run_cpp_sample(case, tmp_path)

    assert result.perf_data_path.exists()
    report_text = read_perf_report(result.perf_data_path)
    caller_text = read_perf_report(result.perf_data_path, call_graph_order="caller")
    callee_text = read_perf_report(result.perf_data_path, call_graph_order="callee")
    script_text = read_perf_script(result.perf_data_path)

    assert_contains_groups(report_text, case.report_groups, context=f"report for {case.name}")
    assert_contains_groups(
        caller_text,
        case.caller_groups,
        context=f"caller report for {case.name}",
    )
    assert_contains_groups(
        callee_text,
        case.callee_groups,
        context=f"callee report for {case.name}",
    )
    assert_contains_groups(script_text, case.script_groups, context=f"perf script for {case.name}")
    assert_contains_ordered_chains(
        caller_text,
        case.caller_chains,
        context=f"caller report for {case.name}",
    )
    assert_contains_ordered_chains(
        callee_text,
        case.callee_chains,
        context=f"callee report for {case.name}",
    )
