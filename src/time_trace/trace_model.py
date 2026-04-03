from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TraceEvent:
    name: str
    label: str
    start_us: int
    duration_us: int
    category: str | None = None
    detail: str | None = None

    @property
    def end_us(self) -> int:
        return self.start_us + self.duration_us


@dataclass
class CallTreeNode:
    name: str
    label: str
    start_us: int
    duration_us: int
    phase: str
    detail: str | None = None
    self_us: int = 0
    children: list[CallTreeNode] = field(default_factory=list)

    @property
    def end_us(self) -> int:
        return self.start_us + self.duration_us


@dataclass(frozen=True)
class ReplayNode:
    symbol_name: str
    display_label: str
    self_iterations: int
    children: tuple[ReplayNode, ...] = ()

    @property
    def total_iterations(self) -> int:
        return self.self_iterations + sum(child.total_iterations for child in self.children)


@dataclass(frozen=True)
class ProfileRequest:
    compiler_argv: list[str]
    output_dir: Path | None = None
    keep_trace: bool = False
    emit_intermediate: bool = False
    max_nodes: int = 512
    loop_budget: int = 120_000_000
    sample_frequency: int | None = None
    replay_compiler: str = "clang"
    perf_binary: str = "perf"
