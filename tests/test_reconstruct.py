import pytest

from time_trace.reconstruct import build_call_tree, filter_events, list_event_names, list_event_tags
from time_trace.trace_model import CallTreeNode, TraceEvent


def test_build_call_tree_groups_disjoint_phases() -> None:
    events = [
        TraceEvent(name="ParseClass", label="ParseClass: foo.hpp:1:1", start_us=0, duration_us=80),
        TraceEvent(name="InstantiateClass", label="Foo<int>", start_us=10, duration_us=20),
        TraceEvent(name="Backend", label="codegen", start_us=100, duration_us=40),
    ]

    root = build_call_tree(events, max_nodes=16)

    assert [child.label for child in root.children] == ["clang frontend", "codegen"]
    assert root.children[0].children[0].label == "ParseClass: foo.hpp:1:1"


def test_build_call_tree_inserts_template_phase_group() -> None:
    events = [
        TraceEvent(name="Frontend", label="clang frontend", start_us=0, duration_us=120),
        TraceEvent(
            name="ParseClass",
            label="ParseClass: foo.hpp:1:1",
            start_us=5,
            duration_us=100,
        ),
        TraceEvent(
            name="InstantiateClass",
            label="Foo<int>",
            start_us=20,
            duration_us=30,
        ),
    ]

    root = build_call_tree(events, max_nodes=16)

    frontend = root.children[0]
    assert frontend.label == "clang frontend"
    parse_class = frontend.children[0]
    assert parse_class.label == "ParseClass: foo.hpp:1:1"
    assert parse_class.children[0].label == "template"
    assert parse_class.children[0].children[0].label == "Foo<int>"


def test_build_call_tree_keeps_all_nodes_by_default() -> None:
    events = [
        TraceEvent(name=f"ParseClass{i}", label=f"Node {i}", start_us=i * 10, duration_us=10)
        for i in range(10)
    ]

    root = build_call_tree(events)

    assert _count_nodes(root) == 12


def test_build_call_tree_prunes_to_max_nodes() -> None:
    events = [
        TraceEvent(name=f"ParseClass{i}", label=f"Node {i}", start_us=i * 10, duration_us=10)
        for i in range(10)
    ]

    root = build_call_tree(events, max_nodes=4)

    total_nodes = _count_nodes(root)
    assert total_nodes <= 4


def test_filter_events_matches_include_patterns() -> None:
    events = [
        TraceEvent(
            name="InstantiateClass",
            label="dingo::container<...>::register_type<...>",
            start_us=0,
            duration_us=5,
        ),
        TraceEvent(
            name="RunPass",
            label="RunPass: foo",
            start_us=5,
            duration_us=5,
        ),
    ]

    filtered = filter_events(
        events,
        include_patterns=("tag:template", "label:*register_type*"),
    )

    assert [event.name for event in filtered] == ["InstantiateClass"]


def test_filter_events_applies_excludes_after_includes() -> None:
    events = [
        TraceEvent(name="InstantiateClass", label="Foo<int>", start_us=0, duration_us=5),
        TraceEvent(name="InstantiateFunction", label="Bar<int>", start_us=5, duration_us=5),
    ]

    filtered = filter_events(
        events,
        include_patterns=("tag:template",),
        exclude_patterns=("label:Bar*",),
    )

    assert [event.label for event in filtered] == ["Foo<int>"]


def test_filter_events_rejects_empty_result() -> None:
    events = [
        TraceEvent(name="RunPass", label="RunPass: foo", start_us=0, duration_us=5),
    ]

    with pytest.raises(ValueError, match="excluded all"):
        filter_events(events, include_patterns=("tag:template",))


def test_list_event_names_and_tags() -> None:
    events = [
        TraceEvent(name="InstantiateClass", label="Foo<int>", start_us=0, duration_us=5),
        TraceEvent(name="RunPass", label="RunPass: foo", start_us=5, duration_us=5),
    ]

    assert list_event_names(events) == ("InstantiateClass", "RunPass")
    assert list_event_tags(events) == (
        "backend",
        "codegen",
        "frontend",
        "template",
    )


def _count_nodes(root: CallTreeNode) -> int:
    return 1 + sum(_count_nodes(child) for child in root.children)
