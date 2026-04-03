from __future__ import annotations

from collections import defaultdict

from .trace_model import CallTreeNode, ReplayNode


def build_replay_plan(root: CallTreeNode, *, target_iterations: int = 120_000_000) -> ReplayNode:
    if target_iterations <= 0:
        raise ValueError("target_iterations must be positive")

    total_self_us = max(1, _sum_self_time(root))
    scale = target_iterations / total_self_us
    symbol_counts: defaultdict[str, int] = defaultdict(int)
    return _convert_node(root, scale=scale, symbol_counts=symbol_counts)


def _sum_self_time(node: CallTreeNode) -> int:
    return node.self_us + sum(_sum_self_time(child) for child in node.children)


def _convert_node(
    node: CallTreeNode,
    *,
    scale: float,
    symbol_counts: defaultdict[str, int],
) -> ReplayNode:
    symbol_name = _unique_symbol_name(node.label, symbol_counts)
    self_iterations = 0
    if node.self_us > 0:
        self_iterations = max(1, round(node.self_us * scale))

    children = tuple(
        _convert_node(child, scale=scale, symbol_counts=symbol_counts)
        for child in sorted(node.children, key=lambda current: current.duration_us, reverse=True)
    )

    return ReplayNode(
        symbol_name=symbol_name,
        display_label=node.label,
        self_iterations=self_iterations,
        children=children,
    )


def _unique_symbol_name(label: str, symbol_counts: defaultdict[str, int]) -> str:
    symbol_counts[label] += 1
    if symbol_counts[label] == 1:
        return label
    return f"{label} [{symbol_counts[label]}]"
