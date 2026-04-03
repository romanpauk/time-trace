from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .trace_model import CallTreeNode, PlannedSample, SamplingPlan, SymbolDefinition

_DEFAULT_SAMPLE_FREQUENCY = 4_000


@dataclass(frozen=True)
class _SymbolizedNode:
    node: CallTreeNode
    symbol_name: str
    children: tuple[_SymbolizedNode, ...]


def build_sampling_plan(root: CallTreeNode, *, sample_frequency: int | None = None) -> SamplingPlan:
    frequency = sample_frequency or _DEFAULT_SAMPLE_FREQUENCY
    if frequency <= 0:
        raise ValueError("sample_frequency must be positive when provided")

    symbol_counts: defaultdict[str, int] = defaultdict(int)
    symbols: list[SymbolDefinition] = []
    symbolized_root = _symbolize_tree(root, symbol_counts=symbol_counts, symbols=symbols)

    duration_us = max(1, root.duration_us)
    sample_count = max(1, round(duration_us * frequency / 1_000_000))
    duration_ns = max(1, duration_us * 1_000)
    samples = tuple(
        PlannedSample(
            timestamp_ns=offset_ns + 1,
            period=1,
            stack_symbols=_resolve_active_stack(
                symbolized_root,
                timestamp_ns=offset_ns,
                root_start_us=root.start_us,
            ),
        )
        for offset_ns in _sample_offsets(duration_ns=duration_ns, sample_count=sample_count)
    )

    return SamplingPlan(
        root_symbol_name=symbolized_root.symbol_name,
        total_duration_us=duration_us,
        sample_count=sample_count,
        symbols=tuple(symbols),
        samples=samples,
    )


def _symbolize_tree(
    node: CallTreeNode,
    *,
    symbol_counts: defaultdict[str, int],
    symbols: list[SymbolDefinition],
) -> _SymbolizedNode:
    symbol_name = _unique_symbol_name(node.label, symbol_counts)
    symbols.append(SymbolDefinition(symbol_name=symbol_name, display_label=node.label))
    children = tuple(
        _symbolize_tree(child, symbol_counts=symbol_counts, symbols=symbols)
        for child in node.children
    )
    return _SymbolizedNode(node=node, symbol_name=symbol_name, children=children)


def _sample_offsets(*, duration_ns: int, sample_count: int) -> tuple[int, ...]:
    offsets: list[int] = []
    for index in range(sample_count):
        midpoint_ns = ((2 * index + 1) * duration_ns) // (2 * sample_count)
        offsets.append(min(duration_ns - 1, midpoint_ns))
    return tuple(offsets)


def _resolve_active_stack(
    node: _SymbolizedNode,
    *,
    timestamp_ns: int,
    root_start_us: int,
) -> tuple[str, ...]:
    matching_children = [
        child
        for child in node.children
        if _contains_timestamp(child.node, timestamp_ns=timestamp_ns, root_start_us=root_start_us)
    ]
    if not matching_children:
        return (node.symbol_name,)

    active_child = max(
        matching_children,
        key=lambda child: (child.node.start_us, child.node.duration_us, child.symbol_name),
    )
    return (
        *_resolve_active_stack(
            active_child,
            timestamp_ns=timestamp_ns,
            root_start_us=root_start_us,
        ),
        node.symbol_name,
    )


def _contains_timestamp(
    node: CallTreeNode,
    *,
    timestamp_ns: int,
    root_start_us: int,
) -> bool:
    start_ns = (node.start_us - root_start_us) * 1_000
    end_ns = start_ns + max(1, node.duration_us * 1_000)
    return start_ns <= timestamp_ns < end_ns


def _unique_symbol_name(label: str, symbol_counts: defaultdict[str, int]) -> str:
    symbol_counts[label] += 1
    if symbol_counts[label] == 1:
        return label
    return f"{label} [{symbol_counts[label]}]"
