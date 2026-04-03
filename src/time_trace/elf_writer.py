from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .trace_model import MappedSymbol, SamplingPlan, SyntheticElfLayout


def emit_synthetic_elf(
    plan: SamplingPlan,
    *,
    output_dir: Path,
    compiler: str,
    base_address: int,
    keep_intermediate: bool = False,
) -> SyntheticElfLayout:
    output_dir.mkdir(parents=True, exist_ok=True)
    ir_path = output_dir / "synthetic-image.ll"
    image_path = output_dir / "synthetic-image.so"
    ir_path.write_text(render_symbol_ir(plan))

    nm_binary = shutil.which("nm")
    if nm_binary is None:
        raise RuntimeError("failed to locate 'nm'; it is required for synthetic symbol mapping")

    command = [
        compiler,
        "-shared",
        "-x",
        "ir",
        "-g",
        "-O0",
        "-fno-omit-frame-pointer",
        "-nostdlib",
        "-Wl,--build-id=sha1",
        "-o",
        str(image_path),
        str(ir_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"failed to build synthetic ELF: {' '.join(command)}\n{stderr}".strip())

    symbols = _read_symbol_table(
        plan,
        image_path=image_path,
        base_address=base_address,
        nm_binary=nm_binary,
    )
    if not keep_intermediate:
        ir_path.unlink(missing_ok=True)

    return SyntheticElfLayout(
        image_path=image_path.resolve(),
        ir_path=ir_path.resolve(),
        symbols=symbols,
        base_address=base_address,
    )


def render_symbol_ir(plan: SamplingPlan) -> str:
    lines = ['source_filename = "time-trace-synthetic-symbols"', ""]
    for symbol in plan.symbols:
        lines.extend(
            [
                f"define void @{_llvm_name(symbol.symbol_name)}() #0 {{",
                "entry:",
                "  ret void",
                "}",
                "",
            ]
        )
    lines.append('attributes #0 = { noinline nounwind optnone "frame-pointer"="all" }')
    lines.append("")
    return "\n".join(lines)


def _read_symbol_table(
    plan: SamplingPlan,
    *,
    image_path: Path,
    base_address: int,
    nm_binary: str,
) -> tuple[MappedSymbol, ...]:
    wanted = {symbol.symbol_name for symbol in plan.symbols}
    completed = subprocess.run(
        [nm_binary, "-S", "-n", str(image_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"failed to read synthetic ELF symbols: {stderr}".strip())

    found: dict[str, tuple[int, int]] = {}
    for line in completed.stdout.splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) != 4:
            continue
        address_hex, size_hex, symbol_type, symbol_name = parts
        if symbol_type not in {"T", "t"} or symbol_name not in wanted:
            continue
        found[symbol_name] = (base_address + int(address_hex, 16), max(1, int(size_hex, 16)))

    missing = [symbol.symbol_name for symbol in plan.symbols if symbol.symbol_name not in found]
    if missing:
        missing_labels = ", ".join(missing)
        raise RuntimeError(f"synthetic ELF did not contain expected symbols: {missing_labels}")

    return tuple(
        MappedSymbol(
            symbol_name=symbol.symbol_name,
            display_label=symbol.display_label,
            address=found[symbol.symbol_name][0],
            size=found[symbol.symbol_name][1],
        )
        for symbol in plan.symbols
    )


def _llvm_name(symbol_name: str) -> str:
    escaped: list[str] = []
    for char in symbol_name:
        code_point = ord(char)
        if char in {'"', "\\"} or code_point < 0x20 or code_point > 0x7E:
            escaped.append(f"\\{code_point:02X}")
        else:
            escaped.append(char)
    return '"' + "".join(escaped) + '"'
