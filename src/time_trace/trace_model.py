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
class SymbolDefinition:
    symbol_name: str
    display_label: str


@dataclass(frozen=True)
class PlannedSample:
    timestamp_ns: int
    period: int
    stack_symbols: tuple[str, ...]

    @property
    def leaf_symbol(self) -> str:
        return self.stack_symbols[0]


@dataclass(frozen=True)
class SamplingPlan:
    root_symbol_name: str
    total_duration_us: int
    sample_count: int
    symbols: tuple[SymbolDefinition, ...]
    samples: tuple[PlannedSample, ...]


@dataclass(frozen=True)
class MappedSymbol:
    symbol_name: str
    display_label: str
    address: int
    size: int


@dataclass(frozen=True)
class SyntheticElfLayout:
    image_path: Path
    ir_path: Path
    symbols: tuple[MappedSymbol, ...]
    base_address: int


@dataclass(frozen=True)
class ProfileRequest:
    compiler_argv: list[str]
    output_dir: Path | None = None
    keep_trace: bool = False
    emit_intermediate: bool = False
    max_nodes: int = 512
    sample_frequency: int | None = None
