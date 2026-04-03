from __future__ import annotations

import json
from pathlib import Path

import pytest

from time_trace.trace_loader import TraceFormatError, load_trace


def test_load_trace_filters_totals_and_metadata(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "traceEvents": [
                    {"name": "process_name", "ph": "M", "ts": 0, "args": {"name": "clang"}},
                    {"name": "Total Frontend", "ph": "X", "ts": 0, "dur": 123},
                    {"name": "Frontend", "ph": "X", "ts": 10, "dur": 30},
                    {
                        "name": "InstantiateClass",
                        "ph": "X",
                        "ts": 12,
                        "dur": 10,
                        "args": {"detail": "std::tuple<int>"},
                    },
                ]
            }
        )
    )

    events = load_trace(trace_path)

    assert [event.label for event in events] == ["clang frontend", "std::tuple<int>"]


def test_load_trace_rejects_bad_json(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text("not-json")

    with pytest.raises(TraceFormatError):
        load_trace(trace_path)
