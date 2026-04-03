from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CppSampleCase:
    name: str
    source_name: str
    language_standard: str = "c++20"
    extra_args: tuple[str, ...] = ()
    report_groups: tuple[tuple[str, ...], ...] = ()
    script_groups: tuple[tuple[str, ...], ...] = ()
    caller_groups: tuple[tuple[str, ...], ...] = ()
    callee_groups: tuple[tuple[str, ...], ...] = ()
    caller_chains: tuple[tuple[str, ...], ...] = ()
    callee_chains: tuple[tuple[str, ...], ...] = ()

    @property
    def source_path(self) -> Path:
        return Path("tests") / "cpp_samples" / self.source_name


CPP_SAMPLE_CASES: tuple[CppSampleCase, ...] = (
    CppSampleCase(
        name="variant-visit",
        source_name="variant_visit.cpp",
        report_groups=(
            ("clang frontend",),
            ("template",),
            ("VariantDispatcher", "VariantPayload", "SampleVariant"),
        ),
        script_groups=(("VariantDispatcher", "VariantPayload", "SampleVariant"),),
        caller_groups=(
            ("clang frontend",),
            ("VariantDispatcher", "VariantPayload", "SampleVariant"),
        ),
        callee_groups=(
            ("template", "clang frontend"),
            ("VariantDispatcher", "VariantPayload", "SampleVariant"),
        ),
        caller_chains=(("template", "VariantDispatcher", "std::visit<"),),
        callee_chains=(("VariantDispatcher", "template", "clang frontend"),),
    ),
    CppSampleCase(
        name="tuple-meta",
        source_name="tuple_meta.cpp",
        report_groups=(
            ("clang frontend",),
            ("template",),
            ("ValueAt<", "MakeSequence<", "ValueList<"),
        ),
        script_groups=(("ValueAt<", "MakeSequence<", "ValueList<"),),
        caller_groups=(
            ("clang frontend",),
            ("ValueAt<", "MakeSequence<", "ValueList<"),
        ),
        callee_groups=(
            ("template", "clang frontend"),
            ("ValueAt<", "MakeSequence<", "ValueList<"),
        ),
        caller_chains=(("template", "ValueAt<100,", "ValueAt<99,"),),
        callee_chains=(("ValueAt<100,", "template", "clang frontend", "clang++ compilation"),),
    ),
    CppSampleCase(
        name="ranges-pipeline",
        source_name="ranges_pipeline.cpp",
        report_groups=(("clang frontend",), ("RangeProjection", "RangeBox", "consume_range")),
        script_groups=(("RangeProjection", "RangeBox", "consume_range"),),
        caller_groups=(("clang frontend",), ("RangeProjection", "RangeBox", "consume_range")),
        callee_groups=(
            ("clang frontend", "codegen", "template"),
            ("RangeProjection", "RangeBox", "consume_range"),
        ),
        caller_chains=(("template", "consume_range<", "RangeProjection<"),),
        callee_chains=(
            (
                "RangeProjection<",
                "consume_range<",
                "PerformPendingInstantiations",
                "template",
                "clang frontend",
            ),
        ),
    ),
)
