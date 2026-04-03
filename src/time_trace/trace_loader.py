from __future__ import annotations

import json
from pathlib import Path

from .trace_model import TraceEvent

_PHASE_ROOT_LABELS = {
    "Frontend": "clang frontend",
    "Backend": "codegen",
}


class TraceFormatError(ValueError):
    """Raised when clang's trace file cannot be parsed."""


def load_trace(trace_path: Path) -> list[TraceEvent]:
    try:
        payload = json.loads(trace_path.read_text())
    except FileNotFoundError as exc:
        raise TraceFormatError(f"trace file not found: {trace_path}") from exc
    except json.JSONDecodeError as exc:
        raise TraceFormatError(f"invalid JSON in trace file: {trace_path}") from exc

    raw_events = payload.get("traceEvents")
    if not isinstance(raw_events, list):
        raise TraceFormatError("clang time-trace JSON did not contain a traceEvents array")

    events: list[TraceEvent] = []
    for raw in raw_events:
        if not isinstance(raw, dict):
            continue
        if raw.get("ph") != "X":
            continue

        name = str(raw.get("name") or "")
        if not name or name.startswith("Total "):
            continue

        start_us = _coerce_int(raw.get("ts"))
        duration_us = _coerce_int(raw.get("dur"))
        if start_us is None or duration_us is None or duration_us <= 0:
            continue

        args = raw.get("args") if isinstance(raw.get("args"), dict) else {}
        detail = args.get("detail") if isinstance(args, dict) else None
        label = build_display_label(name, detail if isinstance(detail, str) else None)
        events.append(
            TraceEvent(
                name=name,
                label=label,
                start_us=start_us,
                duration_us=duration_us,
                category=raw.get("cat") if isinstance(raw.get("cat"), str) else None,
                detail=detail if isinstance(detail, str) else None,
            )
        )

    if not events:
        raise TraceFormatError("no complete ('X') clang time-trace events were found")

    return sorted(events, key=lambda event: (event.start_us, -event.duration_us, event.label))


def build_display_label(name: str, detail: str | None) -> str:
    if name in _PHASE_ROOT_LABELS:
        return _PHASE_ROOT_LABELS[name]
    if detail:
        if name.startswith("Instantiate"):
            return detail
        if _looks_like_source_location(detail):
            return f"{name}: {_shorten_source_location(detail)}"
        return f"{name}: {detail}"
    return name


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _looks_like_source_location(detail: str) -> bool:
    return "/" in detail and ":" in detail


def _shorten_source_location(detail: str) -> str:
    path_part, _, remainder = detail.rpartition("/")
    if not path_part:
        return detail
    return f"{remainder}"
