from time_trace.reconstruct import build_call_tree
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


def test_build_call_tree_inserts_template_instantiation_phase_group() -> None:
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
    assert parse_class.children[0].label == "template instantiation"
    assert parse_class.children[0].children[0].label == "Foo<int>"


def test_build_call_tree_prunes_to_max_nodes() -> None:
    events = [
        TraceEvent(name=f"ParseClass{i}", label=f"Node {i}", start_us=i * 10, duration_us=10)
        for i in range(10)
    ]

    root = build_call_tree(events, max_nodes=4)

    total_nodes = _count_nodes(root)
    assert total_nodes <= 4


def _count_nodes(root: CallTreeNode) -> int:
    return 1 + sum(_count_nodes(child) for child in root.children)
