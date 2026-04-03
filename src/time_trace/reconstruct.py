from __future__ import annotations

import heapq
from collections import defaultdict

from .trace_model import CallTreeNode, TraceEvent

_PHASE_LABELS = {
    "frontend": "clang frontend",
    "instantiation": "template instantiation",
    "codegen": "codegen",
}
_INSTANTIATION_NAMES = {"PerformPendingInstantiations"}
_CODEGEN_NAMES = {
    "Backend",
    "CodeGenPasses",
    "ModuleToFunctionPassAdaptor",
    "OptFunction",
    "OptModule",
    "Optimizer",
}
PathKey = tuple[int, ...]
RankedNode = tuple[int, int, PathKey]


def build_call_tree(events: list[TraceEvent], *, max_nodes: int = 512) -> CallTreeNode:
    root = CallTreeNode(
        name="root",
        label="clang++ compilation",
        start_us=min(event.start_us for event in events),
        duration_us=max(event.end_us for event in events) - min(event.start_us for event in events),
        phase="root",
    )

    stack: list[CallTreeNode] = [root]
    for event in events:
        while len(stack) > 1 and event.start_us >= stack[-1].end_us:
            stack.pop()

        while len(stack) > 1 and not _contains(stack[-1], event):
            stack.pop()

        node = CallTreeNode(
            name=event.name,
            label=event.label,
            start_us=event.start_us,
            duration_us=event.duration_us,
            phase=classify_phase(event.name),
            detail=event.detail,
        )
        stack[-1].children.append(node)
        stack.append(node)

    _compute_self_time(root)
    root = _unwrap_execute_compiler(root)
    root = _inject_phase_groups(root)
    root = _prune_tree(root, max_nodes=max_nodes)
    _compute_self_time(root)
    return root


def classify_phase(name: str) -> str:
    if name.startswith("Instantiate") or name in _INSTANTIATION_NAMES:
        return "instantiation"
    if name in _CODEGEN_NAMES or name.startswith("Opt") or name.startswith("CodeGen"):
        return "codegen"
    return "frontend"


def _contains(node: CallTreeNode, event: TraceEvent) -> bool:
    return node.start_us <= event.start_us and event.end_us <= node.end_us


def _compute_self_time(node: CallTreeNode) -> None:
    for child in node.children:
        _compute_self_time(child)
    node.self_us = max(0, node.duration_us - sum(child.duration_us for child in node.children))


def _unwrap_execute_compiler(root: CallTreeNode) -> CallTreeNode:
    if len(root.children) != 1 or root.children[0].name != "ExecuteCompiler":
        return root

    execute = root.children[0]
    return CallTreeNode(
        name=root.name,
        label=root.label,
        start_us=execute.start_us,
        duration_us=execute.duration_us,
        phase=root.phase,
        detail=execute.detail,
        self_us=execute.self_us,
        children=execute.children,
    )


def _inject_phase_groups(node: CallTreeNode) -> CallTreeNode:
    grouped_children: dict[str, list[CallTreeNode]] = defaultdict(list)
    passthrough_children: list[CallTreeNode] = []

    for child in (_inject_phase_groups(current) for current in node.children):
        phase_label = _PHASE_LABELS.get(child.phase)
        if child.label == phase_label:
            passthrough_children.append(child)
            continue

        if node.phase == "root":
            grouped_children[child.phase].append(child)
            continue

        if child.phase != node.phase and phase_label is not None:
            grouped_children[child.phase].append(child)
            continue

        passthrough_children.append(child)

    synthetic_children = [
        _build_phase_parent(phase, children)
        for phase, children in grouped_children.items()
        if children
    ]
    return CallTreeNode(
        name=node.name,
        label=node.label,
        start_us=node.start_us,
        duration_us=node.duration_us,
        phase=node.phase,
        detail=node.detail,
        self_us=node.self_us,
        children=sorted(
            [*passthrough_children, *synthetic_children],
            key=_node_sort_key,
        ),
    )


def _build_phase_parent(phase: str, children: list[CallTreeNode]) -> CallTreeNode:
    start_us = min(child.start_us for child in children)
    end_us = max(child.end_us for child in children)
    return CallTreeNode(
        name=_PHASE_LABELS[phase],
        label=_PHASE_LABELS[phase],
        start_us=start_us,
        duration_us=end_us - start_us,
        phase=phase,
        children=sorted(children, key=_node_sort_key),
    )


def _prune_tree(root: CallTreeNode, *, max_nodes: int) -> CallTreeNode:
    if max_nodes <= 0:
        raise ValueError("max_nodes must be positive")

    ranked: list[RankedNode] = []
    _collect_ranked_nodes(root, path=(), ranked=ranked)
    if len(ranked) + 1 <= max_nodes:
        return root

    keep_paths: set[PathKey] = {()}
    for _neg_duration, _neg_self, path in heapq.nsmallest(max_nodes - 1, ranked):
        for index in range(len(path) + 1):
            keep_paths.add(path[:index])

    return _rebuild_pruned(root, path=(), keep_paths=keep_paths)


def _collect_ranked_nodes(
    node: CallTreeNode,
    *,
    path: PathKey,
    ranked: list[RankedNode],
) -> None:
    for child_index, child in enumerate(node.children):
        child_path = (*path, child_index)
        ranked.append((-child.duration_us, -child.self_us, child_path))
        _collect_ranked_nodes(child, path=child_path, ranked=ranked)


def _rebuild_pruned(
    node: CallTreeNode,
    *,
    path: PathKey,
    keep_paths: set[PathKey],
) -> CallTreeNode:
    kept_children: list[CallTreeNode] = []
    folded_self_us = node.self_us
    for child_index, child in enumerate(node.children):
        child_path = (*path, child_index)
        if child_path not in keep_paths:
            folded_self_us += child.duration_us
            continue
        kept_children.append(_rebuild_pruned(child, path=child_path, keep_paths=keep_paths))

    duration_us = folded_self_us + sum(child.duration_us for child in kept_children)
    return CallTreeNode(
        name=node.name,
        label=node.label,
        start_us=node.start_us,
        duration_us=duration_us,
        phase=node.phase,
        detail=node.detail,
        self_us=folded_self_us,
        children=kept_children,
    )


def _node_sort_key(node: CallTreeNode) -> tuple[int, int, str]:
    return (node.start_us, -node.duration_us, node.label)
