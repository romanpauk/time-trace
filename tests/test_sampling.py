from time_trace.sampling import build_replay_plan
from time_trace.trace_model import CallTreeNode


def test_build_replay_plan_assigns_unique_duplicate_names() -> None:
    root = CallTreeNode(
        name="root",
        label="root",
        start_us=0,
        duration_us=10,
        phase="root",
        self_us=0,
        children=[
            CallTreeNode(
                name="child",
                label="duplicate",
                start_us=0,
                duration_us=5,
                phase="frontend",
                self_us=5,
            ),
            CallTreeNode(
                name="child",
                label="duplicate",
                start_us=5,
                duration_us=5,
                phase="frontend",
                self_us=5,
            ),
        ],
    )

    replay = build_replay_plan(root, target_iterations=100)

    assert replay.children[0].symbol_name == "duplicate"
    assert replay.children[1].symbol_name == "duplicate [2]"
