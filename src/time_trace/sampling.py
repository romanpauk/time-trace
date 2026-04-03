from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field

from .trace_model import (
    CallTreeNode,
    PlannedSample,
    SamplingBlueprint,
    SymbolDefinition,
)

_DEFAULT_SAMPLE_FREQUENCY = 4_000


@dataclass(eq=False)
class _SymbolizedNode:
    node: CallTreeNode
    symbol_name: str
    children: tuple[_SymbolizedNode, ...] = ()
    parent: _SymbolizedNode | None = None
    start_ns: int = 0
    end_ns: int = 0
    event_key: tuple[int, int, str] = field(default_factory=lambda: (0, 0, ""))


def build_sampling_stream(
    root: CallTreeNode,
    *,
    sample_frequency: int | None = None,
) -> tuple[SamplingBlueprint, Iterator[PlannedSample]]:
    frequency = _DEFAULT_SAMPLE_FREQUENCY if sample_frequency is None else sample_frequency
    if frequency <= 0:
        raise ValueError("sample_frequency must be positive when provided")

    symbol_counts: defaultdict[str, int] = defaultdict(int)
    symbols: list[SymbolDefinition] = []
    symbolized_root = _symbolize_tree(
        root,
        root_start_us=root.start_us,
        symbol_counts=symbol_counts,
        symbols=symbols,
    )

    duration_us = max(1, root.duration_us)
    sample_count = max(1, round(duration_us * frequency / 1_000_000))
    duration_ns = max(1, duration_us * 1_000)
    return SamplingBlueprint(
        root_symbol_name=symbolized_root.symbol_name,
        total_duration_us=duration_us,
        sample_count=sample_count,
        symbols=tuple(symbols),
    ), _iter_timeline_samples(
        symbolized_root,
        duration_ns=duration_ns,
        sample_count=sample_count,
    )


def _symbolize_tree(
    node: CallTreeNode,
    *,
    root_start_us: int,
    symbol_counts: defaultdict[str, int],
    symbols: list[SymbolDefinition],
    parent: _SymbolizedNode | None = None,
) -> _SymbolizedNode:
    symbol_name = _unique_symbol_name(node.label, symbol_counts)
    symbols.append(SymbolDefinition(symbol_name=symbol_name, display_label=node.label))
    start_ns = max(0, (node.start_us - root_start_us) * 1_000)
    end_ns = start_ns + max(1, node.duration_us * 1_000)
    symbolized = _SymbolizedNode(
        node=node,
        symbol_name=symbol_name,
        parent=parent,
        start_ns=start_ns,
        end_ns=end_ns,
        event_key=(node.start_us, node.duration_us, symbol_name),
    )
    symbolized.children = tuple(
        _symbolize_tree(
            child,
            root_start_us=root_start_us,
            symbol_counts=symbol_counts,
            symbols=symbols,
            parent=symbolized,
        )
        for child in node.children
    )
    return symbolized


def _iter_timeline_samples(
    root: _SymbolizedNode,
    *,
    duration_ns: int,
    sample_count: int,
) -> Iterator[PlannedSample]:
    events, active_children = _build_timeline_state(root)
    removed_children: defaultdict[_SymbolizedNode, set[_SymbolizedNode]] = defaultdict(set)
    current_index = 0
    cached_stack: tuple[str, ...] | None = None

    for offset_ns in _sample_offsets(duration_ns=duration_ns, sample_count=sample_count):
        saw_event = False
        while current_index < len(events) and events[current_index][0] <= offset_ns:
            _, event_kind, parent, child = events[current_index]
            if event_kind == 0:
                heapq.heappush(active_children[parent], _heap_entry(child))
                removed_children[parent].discard(child)
            else:
                removed_children[parent].add(child)
            current_index += 1
            saw_event = True
        if saw_event or cached_stack is None:
            cached_stack = _resolve_stack_from_active_children(
                root,
                active_children,
                removed_children,
            )
        yield PlannedSample(
            timestamp_ns=offset_ns + 1,
            period=1,
            stack_symbols=cached_stack,
        )


def _build_timeline_state(
    root: _SymbolizedNode,
) -> tuple[
    tuple[tuple[int, int, _SymbolizedNode, _SymbolizedNode], ...],
    dict[_SymbolizedNode, list[tuple[tuple[int, int, str], _SymbolizedNode]]],
]:
    events: list[tuple[int, int, _SymbolizedNode, _SymbolizedNode]] = []
    active_children: dict[_SymbolizedNode, list[tuple[tuple[int, int, str], _SymbolizedNode]]] = {}
    for node in _walk_tree(root):
        active_children[node] = []
        if node.parent is None:
            continue
        events.append((node.start_ns, 0, node.parent, node))
        events.append((node.end_ns, 1, node.parent, node))
    events.sort(key=lambda event: (event[0], event[1], event[3].event_key))
    return tuple(events), active_children


def _walk_tree(root: _SymbolizedNode) -> tuple[_SymbolizedNode, ...]:
    nodes: list[_SymbolizedNode] = []
    stack = [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.children))
    return tuple(nodes)


def _resolve_stack_from_active_children(
    root: _SymbolizedNode,
    active_children: dict[_SymbolizedNode, list[tuple[tuple[int, int, str], _SymbolizedNode]]],
    removed_children: defaultdict[_SymbolizedNode, set[_SymbolizedNode]],
) -> tuple[str, ...]:
    stack: list[str] = [root.symbol_name]
    current = root
    while True:
        child = _peek_active_child(current, active_children, removed_children)
        if child is None:
            break
        stack.append(child.symbol_name)
        current = child
    stack.reverse()
    return tuple(stack)


def _peek_active_child(
    parent: _SymbolizedNode,
    active_children: dict[_SymbolizedNode, list[tuple[tuple[int, int, str], _SymbolizedNode]]],
    removed_children: defaultdict[_SymbolizedNode, set[_SymbolizedNode]],
) -> _SymbolizedNode | None:
    heap = active_children[parent]
    removed = removed_children[parent]
    while heap and heap[0][1] in removed:
        _, stale_child = heapq.heappop(heap)
        removed.discard(stale_child)
    if not heap:
        return None
    return heap[0][1]


def _heap_entry(child: _SymbolizedNode) -> tuple[tuple[int, int, str], _SymbolizedNode]:
    start_us, duration_us, symbol_name = child.event_key
    return ((-start_us, -duration_us, symbol_name), child)


def _sample_offsets(*, duration_ns: int, sample_count: int) -> Iterator[int]:
    for index in range(sample_count):
        midpoint_ns = ((2 * index + 1) * duration_ns) // (2 * sample_count)
        yield min(duration_ns - 1, midpoint_ns)


def _unique_symbol_name(label: str, symbol_counts: defaultdict[str, int]) -> str:
    symbol_counts[label] += 1
    if symbol_counts[label] == 1:
        return label
    return f"{label} [{symbol_counts[label]}]"
