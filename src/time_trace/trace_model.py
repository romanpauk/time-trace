from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path


def _validate_sample_frequency(sample_frequency: int | None) -> None:
    if sample_frequency is not None and sample_frequency <= 0:
        raise ValueError("sample_frequency must be positive when provided")


def _validate_max_nodes(max_nodes: int | None) -> None:
    if max_nodes is not None and max_nodes <= 0:
        raise ValueError("max_nodes must be positive when provided")


def _validate_filter_patterns(patterns: tuple[str, ...], *, field_name: str) -> None:
    for value in patterns:
        if not value.strip():
            raise ValueError(f"{field_name} must not contain empty patterns")
        scope, separator, _rest = value.partition(":")
        if separator and scope not in {"name", "label", "tag", "cat"}:
            raise ValueError(
                f"{field_name} pattern {value!r} uses unsupported scope {scope!r}; "
                "expected one of name, label, tag, or cat"
            )


def _normalize_filter_patterns(patterns: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(patterns)


@dataclass(frozen=True)
class TraceEvent:
    name: str
    label: str
    start_us: int
    duration_us: int
    category: str | None = None
    detail: str | None = None

    @property
    def end_us(self) -> int:
        return self.start_us + self.duration_us


@dataclass
class CallTreeNode:
    name: str
    label: str
    start_us: int
    duration_us: int
    phase: str
    detail: str | None = None
    self_us: int = 0
    children: list[CallTreeNode] = field(default_factory=list)

    @property
    def end_us(self) -> int:
        return self.start_us + self.duration_us


@dataclass(frozen=True)
class SymbolDefinition:
    symbol_name: str
    display_label: str


@dataclass(frozen=True)
class PlannedSample:
    timestamp_ns: int
    period: int
    stack_symbols: tuple[str, ...]

    @property
    def leaf_symbol(self) -> str:
        return self.stack_symbols[0]


@dataclass(frozen=True)
class SamplingBlueprint:
    root_symbol_name: str
    total_duration_us: int
    sample_count: int
    symbols: tuple[SymbolDefinition, ...]


@dataclass(frozen=True)
class MappedSymbol:
    symbol_name: str
    display_label: str
    address: int
    size: int


@dataclass(frozen=True)
class SyntheticElfLayout:
    image_path: Path
    ir_path: Path
    symbols: tuple[MappedSymbol, ...]
    base_address: int


@dataclass(frozen=True)
class ProfileRequest:
    compiler_argv: list[str]
    output_dir: Path | None = None
    keep_trace: bool = False
    emit_intermediate: bool = False
    max_nodes: int | None = None
    sample_frequency: int | None = None
    include_patterns: tuple[str, ...] | list[str] = ()
    exclude_patterns: tuple[str, ...] | list[str] = ()

    def __post_init__(self) -> None:
        normalized_include_patterns = _normalize_filter_patterns(self.include_patterns)
        normalized_exclude_patterns = _normalize_filter_patterns(self.exclude_patterns)
        object.__setattr__(self, "include_patterns", normalized_include_patterns)
        object.__setattr__(self, "exclude_patterns", normalized_exclude_patterns)
        _validate_max_nodes(self.max_nodes)
        _validate_sample_frequency(self.sample_frequency)
        _validate_filter_patterns(normalized_include_patterns, field_name="include_patterns")
        _validate_filter_patterns(normalized_exclude_patterns, field_name="exclude_patterns")


def event_matches_filter(
    *,
    event_name: str,
    event_label: str,
    event_category: str | None,
    event_tags: tuple[str, ...],
    patterns: tuple[str, ...],
) -> bool:
    if not patterns:
        return True

    normalized_category = event_category or ""
    for pattern in patterns:
        scope, value = _split_filter_pattern(pattern)
        if scope == "name" and fnmatchcase(event_name, value):
            return True
        if scope == "label" and fnmatchcase(event_label, value):
            return True
        if scope == "tag" and any(fnmatchcase(tag, value) for tag in event_tags):
            return True
        if scope == "cat" and fnmatchcase(normalized_category, value):
            return True
        if scope == "any" and any(
            fnmatchcase(candidate, value)
            for candidate in (event_name, event_label, *event_tags, normalized_category)
        ):
            return True
    return False


def _split_filter_pattern(pattern: str) -> tuple[str, str]:
    scope, separator, value = pattern.partition(":")
    if separator and scope in {"name", "label", "tag", "cat"}:
        return scope, value
    return "any", pattern


def event_tags(event_name: str, event_label: str) -> tuple[str, ...]:
    lower_name = event_name.lower()
    lower_label = event_label.lower()
    tags: list[str] = []

    if event_name.startswith("Instantiate") or event_name == "PerformPendingInstantiations":
        tags.append("template")

    if "overload" in lower_name or "overload" in lower_label:
        tags.extend(("overload", "semantic"))

    if "resolve" in lower_name and "type" not in lower_name:
        tags.extend(("resolution", "semantic"))

    if event_name.startswith("Parse"):
        tags.append("parse")

    if event_name.startswith("Evaluate"):
        tags.extend(("evaluation", "semantic"))

    if event_name.startswith("Debug"):
        tags.append("debug")

    if (
        event_name in {"Backend", "CodeGenPasses", "CodeGen Function", "Optimizer", "RunPass"}
        or event_name.startswith("Opt")
        or event_name.startswith("CodeGen")
        or event_name.endswith("Pass")
        or event_label.startswith("RunPass:")
        or "passmanager<" in lower_label
    ):
        tags.extend(("codegen", "backend"))

    if "codegen" not in tags and "backend" not in tags:
        tags.append("frontend")
    if not tags:
        tags.append("frontend")

    return tuple(dict.fromkeys(tags))
