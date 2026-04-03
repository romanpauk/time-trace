from time_trace.sampling import build_sampling_stream
from time_trace.trace_model import CallTreeNode


def test_build_sampling_stream_assigns_unique_duplicate_names() -> None:
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

    blueprint, samples = build_sampling_stream(root, sample_frequency=1_000_000)
    materialized = tuple(samples)

    assert blueprint.symbols[1].symbol_name == "duplicate"
    assert blueprint.symbols[2].symbol_name == "duplicate [2]"
    assert {sample.leaf_symbol for sample in materialized} == {"duplicate", "duplicate [2]"}
    assert all(
        sample.leaf_symbol == "duplicate" for sample in materialized[: blueprint.sample_count // 2]
    )
    second_half = materialized[blueprint.sample_count // 2 :]
    assert all(sample.leaf_symbol == "duplicate [2]" for sample in second_half)
    timestamps = [sample.timestamp_ns for sample in materialized]
    assert timestamps == sorted(timestamps)


def test_build_sampling_stream_returns_expected_blueprint_and_samples() -> None:
    root = CallTreeNode(
        name="root",
        label="root",
        start_us=0,
        duration_us=10,
        phase="root",
        self_us=0,
        children=[
            CallTreeNode(
                name="child-a",
                label="child-a",
                start_us=0,
                duration_us=5,
                phase="frontend",
                self_us=5,
            ),
            CallTreeNode(
                name="child-b",
                label="child-b",
                start_us=5,
                duration_us=5,
                phase="frontend",
                self_us=5,
            ),
        ],
    )

    blueprint, samples = build_sampling_stream(root, sample_frequency=1_000_000)
    materialized = tuple(samples)

    assert blueprint.root_symbol_name == "root"
    assert blueprint.total_duration_us == 10
    assert blueprint.sample_count == 10
    assert tuple(symbol.symbol_name for symbol in blueprint.symbols) == (
        "root",
        "child-a",
        "child-b",
    )
    assert len(materialized) == blueprint.sample_count
    assert tuple(sample.leaf_symbol for sample in materialized[:5]) == ("child-a",) * 5
    assert tuple(sample.leaf_symbol for sample in materialized[5:]) == ("child-b",) * 5
