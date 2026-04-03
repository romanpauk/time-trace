from time_trace.sampling import build_sampling_plan
from time_trace.trace_model import CallTreeNode


def test_build_sampling_plan_assigns_unique_duplicate_names() -> None:
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

    plan = build_sampling_plan(root, sample_frequency=1_000_000)

    assert plan.symbols[1].symbol_name == "duplicate"
    assert plan.symbols[2].symbol_name == "duplicate [2]"
    assert {sample.leaf_symbol for sample in plan.samples} == {"duplicate", "duplicate [2]"}
    assert all(
        sample.leaf_symbol == "duplicate" for sample in plan.samples[: plan.sample_count // 2]
    )
    assert all(
        sample.leaf_symbol == "duplicate [2]" for sample in plan.samples[plan.sample_count // 2 :]
    )
    timestamps = [sample.timestamp_ns for sample in plan.samples]
    assert timestamps == sorted(timestamps)
