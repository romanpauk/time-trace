from __future__ import annotations

import os
import struct
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .trace_model import PlannedSample, SyntheticElfLayout

PERF_TYPE_SOFTWARE = 1
PERF_COUNT_SW_CPU_CLOCK = 0

PERF_RECORD_COMM = 3
PERF_RECORD_SAMPLE = 9
PERF_RECORD_MMAP2 = 10

PERF_RECORD_MISC_USER = 2

PERF_SAMPLE_IP = 1 << 0
PERF_SAMPLE_TID = 1 << 1
PERF_SAMPLE_TIME = 1 << 2
PERF_SAMPLE_CALLCHAIN = 1 << 5
PERF_SAMPLE_ID = 1 << 6
PERF_SAMPLE_CPU = 1 << 7
PERF_SAMPLE_PERIOD = 1 << 8

_ATTR_FLAG_EXCLUDE_KERNEL = 1 << 5
_ATTR_FLAG_EXCLUDE_HV = 1 << 6
_ATTR_FLAG_COMM = 1 << 9
_ATTR_FLAG_SAMPLE_ID_ALL = 1 << 17
_ATTR_FLAG_MMAP2 = 1 << 28

_PAGE_SIZE = 4_096
_HEADER_SIZE = 104
_U64 = struct.Struct("<Q")
_RECORD_HEADER = struct.Struct("<IHH")
_COMM_PREFIX = struct.Struct("<II")
_MMAP2_PREFIX = struct.Struct("<IIQQQIIQQII")
_SAMPLE_PREFIX = struct.Struct("<QIIQQIIQ")
_SAMPLE_ID = struct.Struct("<IIQQII")
_FILE_ATTR_TRAILER = struct.Struct("<QQ")
_PERF_HEADER_TAIL = struct.Struct("<QQQQQQQQQQQQ")
_PERF_FILE_ATTR = struct.Struct("<IIQQQQQIIQQQQIiQI4x")


@dataclass(frozen=True)
class PerfWriterContract:
    attr_size: int = 112
    event_id: int = 1
    pid: int = 10_001
    tid: int = 10_001
    cpu: int = 0
    base_address: int = 0x1_0000_0000
    comm: str = "time-trace"

    @property
    def header_size(self) -> int:
        return _HEADER_SIZE

    @property
    def sample_type(self) -> int:
        return (
            PERF_SAMPLE_IP
            | PERF_SAMPLE_TID
            | PERF_SAMPLE_TIME
            | PERF_SAMPLE_ID
            | PERF_SAMPLE_CPU
            | PERF_SAMPLE_PERIOD
            | PERF_SAMPLE_CALLCHAIN
        )

    @property
    def attr_flags(self) -> int:
        return (
            _ATTR_FLAG_EXCLUDE_KERNEL
            | _ATTR_FLAG_EXCLUDE_HV
            | _ATTR_FLAG_COMM
            | _ATTR_FLAG_SAMPLE_ID_ALL
            | _ATTR_FLAG_MMAP2
        )


@dataclass(frozen=True)
class PerfFileLayout:
    header_blob: bytes
    ids_blob: bytes
    attrs_blob: bytes
    data_blob: bytes

    @property
    def file_bytes(self) -> bytes:
        return self.header_blob + self.ids_blob + self.attrs_blob + self.data_blob


def build_perf_file_layout(
    contract: PerfWriterContract,
    *,
    synthetic_elf: SyntheticElfLayout,
    samples: Iterable[PlannedSample],
) -> PerfFileLayout:
    ids_blob = _U64.pack(contract.event_id)
    ids_offset = contract.header_size
    attrs_offset = ids_offset + len(ids_blob)
    attrs_blob = _build_perf_file_attr(
        contract,
        ids_offset=ids_offset,
        ids_size=len(ids_blob),
    )

    data_parts = bytearray()
    data_parts.extend(build_comm_record(contract, timestamp_ns=1))
    data_parts.extend(
        build_mmap2_record(
            contract,
            image_path=synthetic_elf.image_path,
            timestamp_ns=2,
        )
    )
    symbol_addresses = {symbol.symbol_name: symbol.address for symbol in synthetic_elf.symbols}
    callchain_cache: dict[tuple[str, ...], tuple[int, bytes]] = {}
    for sample in samples:
        data_parts.extend(
            build_sample_record(
                contract,
                sample=sample,
                symbol_addresses=symbol_addresses,
                callchain_cache=callchain_cache,
            )
        )

    data_blob = bytes(data_parts)
    data_offset = attrs_offset + len(attrs_blob)
    header_blob = build_perf_header(
        attrs_offset=attrs_offset,
        attrs_size=len(attrs_blob),
        data_offset=data_offset,
        data_size=len(data_blob),
    )
    return PerfFileLayout(
        header_blob=header_blob,
        ids_blob=ids_blob,
        attrs_blob=attrs_blob,
        data_blob=data_blob,
    )


def build_perf_header(
    *,
    attrs_offset: int,
    attrs_size: int,
    data_offset: int,
    data_size: int,
) -> bytes:
    return b"PERFILE2" + _PERF_HEADER_TAIL.pack(
        _HEADER_SIZE,
        attrs_size,
        attrs_offset,
        attrs_size,
        data_offset,
        data_size,
        0,
        0,
        0,
        0,
        0,
        0,
    )


def build_comm_record(contract: PerfWriterContract, *, timestamp_ns: int) -> bytes:
    payload = _COMM_PREFIX.pack(contract.pid, contract.tid)
    payload += _encode_c_string(contract.comm)
    payload += _build_sample_id(contract, timestamp_ns=timestamp_ns)
    return _build_record(PERF_RECORD_COMM, PERF_RECORD_MISC_USER, payload)


def build_mmap2_record(
    contract: PerfWriterContract,
    *,
    image_path: Path,
    timestamp_ns: int,
) -> bytes:
    stat_result = image_path.stat()
    payload = _MMAP2_PREFIX.pack(
        contract.pid,
        contract.tid,
        contract.base_address,
        _page_align(stat_result.st_size),
        0,
        os.major(stat_result.st_dev),
        os.minor(stat_result.st_dev),
        stat_result.st_ino,
        0,
        0x5,
        0,
    )
    payload += _encode_c_string(str(image_path.resolve()))
    payload += _build_sample_id(contract, timestamp_ns=timestamp_ns)
    return _build_record(PERF_RECORD_MMAP2, PERF_RECORD_MISC_USER, payload)


def build_sample_record(
    contract: PerfWriterContract,
    *,
    sample: PlannedSample,
    symbol_addresses: dict[str, int],
    callchain_cache: dict[tuple[str, ...], tuple[int, bytes]] | None = None,
) -> bytes:
    if not sample.stack_symbols:
        raise ValueError("planned sample must contain at least one stack frame")

    leaf_address, callchain_payload = _resolve_callchain_payload(
        sample.stack_symbols,
        symbol_addresses=symbol_addresses,
        callchain_cache=callchain_cache,
    )

    payload = _SAMPLE_PREFIX.pack(
        leaf_address,
        contract.pid,
        contract.tid,
        sample.timestamp_ns,
        contract.event_id,
        contract.cpu,
        0,
        sample.period,
    )
    payload += callchain_payload
    return _build_record(PERF_RECORD_SAMPLE, PERF_RECORD_MISC_USER, payload)


def _build_perf_file_attr(
    contract: PerfWriterContract,
    *,
    ids_offset: int,
    ids_size: int,
) -> bytes:
    attr = _PERF_FILE_ATTR.pack(
        PERF_TYPE_SOFTWARE,
        contract.attr_size,
        PERF_COUNT_SW_CPU_CLOCK,
        1,
        contract.sample_type,
        0,
        contract.attr_flags,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )
    if len(attr) != contract.attr_size:
        raise RuntimeError(f"unexpected perf_event_attr size: {len(attr)}")
    return attr + _FILE_ATTR_TRAILER.pack(ids_offset, ids_size)


def _build_record(record_type: int, misc: int, payload: bytes) -> bytes:
    size = 8 + len(payload)
    padding = (8 - (size % 8)) % 8
    return _RECORD_HEADER.pack(record_type, misc, size + padding) + payload + (b"\0" * padding)


def _build_sample_id(contract: PerfWriterContract, *, timestamp_ns: int) -> bytes:
    return _SAMPLE_ID.pack(
        contract.pid,
        contract.tid,
        timestamp_ns,
        contract.event_id,
        contract.cpu,
        0,
    )


def _resolve_callchain_payload(
    stack_symbols: tuple[str, ...],
    *,
    symbol_addresses: dict[str, int],
    callchain_cache: dict[tuple[str, ...], tuple[int, bytes]] | None,
) -> tuple[int, bytes]:
    cached_payload = None if callchain_cache is None else callchain_cache.get(stack_symbols)
    if cached_payload is not None:
        return cached_payload

    try:
        callchain = tuple(symbol_addresses[symbol_name] for symbol_name in stack_symbols)
    except KeyError as exc:
        raise KeyError(f"missing synthetic symbol mapping for {exc.args[0]!r}") from exc

    payload = bytearray()
    payload.extend(_U64.pack(len(callchain)))
    for address in callchain:
        payload.extend(_U64.pack(address))
    resolved = (callchain[0], bytes(payload))
    if callchain_cache is not None:
        callchain_cache[stack_symbols] = resolved
    return resolved


def _encode_c_string(value: str) -> bytes:
    return os.fsencode(value) + b"\0"


def _page_align(value: int) -> int:
    return ((value + _PAGE_SIZE - 1) // _PAGE_SIZE) * _PAGE_SIZE
