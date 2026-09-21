#!/usr/bin/env python3
from __future__ import annotations

import argparse
import struct
from pathlib import Path

FILE_SIGNATURE = 0x08012025
SECTOR_SIZE = 0x1000
DATA_END = 0xFF4
SLOT_SECTORS = 14
CHUNK_SIZES = [0x890, 0xF80, 0xF80, 0xF80, 0xC40] + [0xF80] * 8 + [0x7D0]
SLACK = [DATA_END - size for size in CHUNK_SIZES]
OFFSETS = []
_offset = 0
for size in SLACK:
    OFFSETS.append(_offset)
    _offset += size
SIDECAR_SIZE = 0x1800
assert sum(SLACK) == 6200
assert SIDECAR_SIZE <= sum(SLACK)


def checksum(data: bytes, size: int) -> int:
    total = 0
    for off in range(0, size // 4 * 4, 4):
        total = (total + struct.unpack_from("<I", data, off)[0]) & 0xFFFFFFFF
    return ((total >> 16) + total) & 0xFFFF


def slot_info(data: bytes, slot: int):
    rows = []
    base = slot * SLOT_SECTORS
    for physical in range(base, base + SLOT_SECTORS):
        start = physical * SECTOR_SIZE
        sector = data[start:start + SECTOR_SIZE]
        sid, stored, sig, counter = struct.unpack_from("<HHII", sector, DATA_END)
        valid = sig == FILE_SIGNATURE and sid < SLOT_SECTORS and checksum(sector, CHUNK_SIZES[sid]) == stored
        rows.append((physical, sid, counter, valid))
    valid_rows = [row for row in rows if row[3]]
    ids = sorted(row[1] for row in valid_rows)
    complete = len(valid_rows) == SLOT_SECTORS and ids == list(range(SLOT_SECTORS))
    counters = sorted({row[2] for row in valid_rows})
    return rows, complete, counters


def active_slot(data: bytes) -> int:
    infos = []
    for slot in range(2):
        rows, complete, counters = slot_info(data, slot)
        if complete:
            infos.append((max(counters), slot, rows))
    if not infos:
        raise ValueError("no complete Ruby save slot")
    return max(infos)[1]


def inject(data: bytes, payload: bytes) -> bytes:
    if len(payload) != SIDECAR_SIZE:
        raise ValueError(f"payload must be {SIDECAR_SIZE} bytes")
    out = bytearray(data)
    slot = active_slot(data)
    rows, _, _ = slot_info(data, slot)
    for physical, sid, counter, valid in rows:
        if not valid:
            raise ValueError("active slot unexpectedly contains an invalid sector")
        start = physical * SECTOR_SIZE
        chunk = CHUNK_SIZES[sid]
        offset = OFFSETS[sid]
        count = min(SLACK[sid], SIDECAR_SIZE - offset) if offset < SIDECAR_SIZE else 0
        if count:
            out[start + chunk:start + chunk + count] = payload[offset:offset + count]
    return bytes(out)


def extract(data: bytes) -> bytes:
    slot = active_slot(data)
    result = bytearray(SIDECAR_SIZE)
    rows, _, _ = slot_info(data, slot)
    for physical, sid, counter, valid in rows:
        if not valid:
            raise ValueError("active slot unexpectedly contains an invalid sector")
        start = physical * SECTOR_SIZE
        chunk = CHUNK_SIZES[sid]
        offset = OFFSETS[sid]
        count = min(SLACK[sid], SIDECAR_SIZE - offset) if offset < SIDECAR_SIZE else 0
        if count:
            result[offset:offset + count] = data[start + chunk:start + chunk + count]
    return bytes(result)


def verify(path: Path) -> None:
    original = path.read_bytes()
    if len(original) != 0x20000:
        raise ValueError(f"{path}: expected 128 KiB save")
    payload = bytes(((i * 37 + 0x52) & 0xFF) for i in range(SIDECAR_SIZE))
    modified = inject(original, payload)
    if extract(modified) != payload:
        raise ValueError(f"{path}: sidecar round-trip mismatch")

    slot = active_slot(original)
    rows, _, _ = slot_info(original, slot)
    for physical, sid, counter, valid in rows:
        start = physical * SECTOR_SIZE
        chunk = CHUNK_SIZES[sid]
        if original[start:start + chunk] != modified[start:start + chunk]:
            raise ValueError(f"{path}: vanilla chunk changed for section {sid}")
        if original[start + DATA_END:start + SECTOR_SIZE] != modified[start + DATA_END:start + SECTOR_SIZE]:
            raise ValueError(f"{path}: vanilla footer changed for section {sid}")
        stored = struct.unpack_from("<H", modified, start + DATA_END + 2)[0]
        calc = checksum(modified[start:start + SECTOR_SIZE], chunk)
        if stored != calc:
            raise ValueError(f"{path}: vanilla checksum invalid after sidecar injection for section {sid}")

    if original[28 * SECTOR_SIZE:] != modified[28 * SECTOR_SIZE:]:
        raise ValueError(f"{path}: reserved sectors 28-31 changed")
    print(f"OK {path.name}: slot={slot + 1}, sidecar={SIDECAR_SIZE}, vanilla checksums preserved")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("saves", nargs="+", type=Path)
    args = ap.parse_args()
    for path in args.saves:
        verify(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
