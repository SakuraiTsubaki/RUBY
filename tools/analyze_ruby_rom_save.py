#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

FILE_SIGNATURE = 0x08012025
SECTOR_SIZE = 0x1000
SECTOR_DATA_END = 0xFF4
SAVE_SLOT_SECTORS = 14
TOTAL_FLASH_SECTORS = 32
# Verified against pret/pokeruby@63a8cbf... and all supplied Ruby saves.
CHUNK_SIZES = [0x890, 0xF80, 0xF80, 0xF80, 0xC40] + [0xF80] * 8 + [0x7D0]


def hashes(data: bytes) -> dict:
    return {
        "size": len(data),
        "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def gba_header(data: bytes) -> dict:
    if len(data) < 0xC0:
        raise ValueError("file is too small for a GBA header")

    def ascii_field(blob: bytes) -> str:
        return blob.split(b"\0", 1)[0].decode("ascii", "replace")

    return {
        "title": ascii_field(data[0xA0:0xAC]),
        "game_code": data[0xAC:0xB0].decode("ascii", "replace"),
        "maker_code": data[0xB0:0xB2].decode("ascii", "replace"),
        "fixed_value": data[0xB2],
        "unit_code": data[0xB3],
        "device_type": data[0xB4],
        "software_version": data[0xBC],
        "header_checksum": data[0xBD],
    }


def ruby_checksum(data: bytes, size: int) -> int:
    checksum = 0
    for off in range(0, (size // 4) * 4, 4):
        checksum = (checksum + struct.unpack_from("<I", data, off)[0]) & 0xFFFFFFFF
    return ((checksum >> 16) + checksum) & 0xFFFF


def analyze_rom(path: Path) -> dict:
    data = path.read_bytes()
    last_non_ff = max((i for i, value in enumerate(data) if value != 0xFF), default=-1)
    trailing_ff = len(data) - last_non_ff - 1
    return {
        "kind": "rom",
        "file": path.name,
        **hashes(data),
        "header": gba_header(data),
        "last_non_ff_offset": last_non_ff,
        "trailing_ff_bytes": trailing_ff,
    }


def analyze_save(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) != TOTAL_FLASH_SECTORS * SECTOR_SIZE:
        raise ValueError(f"{path}: expected 128 KiB Ruby flash save, got {len(data)} bytes")

    sectors = []
    for physical in range(TOTAL_FLASH_SECTORS):
        sector = data[physical * SECTOR_SIZE:(physical + 1) * SECTOR_SIZE]
        section_id, stored_checksum, signature, counter = struct.unpack_from("<HHII", sector, SECTOR_DATA_END)
        row = {
            "physical_sector": physical,
            "section_id": section_id,
            "stored_checksum": stored_checksum,
            "signature": f"{signature:08x}",
            "counter": counter,
            "signature_valid": signature == FILE_SIGNATURE,
        }
        if signature == FILE_SIGNATURE and section_id < SAVE_SLOT_SECTORS:
            chunk_size = CHUNK_SIZES[section_id]
            calculated = ruby_checksum(sector, chunk_size)
            slack = sector[chunk_size:SECTOR_DATA_END]
            row.update({
                "chunk_size": chunk_size,
                "calculated_checksum": calculated,
                "checksum_valid": calculated == stored_checksum,
                "slack_bytes": len(slack),
                "slack_nonzero_bytes": sum(value != 0 for value in slack),
            })
        sectors.append(row)

    slots = []
    for slot_index in range(2):
        physical = sectors[slot_index * SAVE_SLOT_SECTORS:(slot_index + 1) * SAVE_SLOT_SECTORS]
        valid = [
            row for row in physical
            if row.get("signature_valid") and row.get("checksum_valid") and row["section_id"] < SAVE_SLOT_SECTORS
        ]
        ids = sorted({row["section_id"] for row in valid})
        counters = sorted({row["counter"] for row in valid})
        slots.append({
            "slot": slot_index + 1,
            "complete": len(valid) == SAVE_SLOT_SECTORS and ids == list(range(SAVE_SLOT_SECTORS)),
            "counters": counters,
            "physical_section_order": [row["section_id"] if row.get("signature_valid") else None for row in physical],
            "valid_section_ids": ids,
        })

    complete = [slot for slot in slots if slot["complete"]]
    active_slot = None
    if complete:
        active_slot = max(complete, key=lambda slot: max(slot["counters"] or [-1]))["slot"]

    active_slack_nonzero = None
    if active_slot is not None:
        active_physical = sectors[(active_slot - 1) * SAVE_SLOT_SECTORS:active_slot * SAVE_SLOT_SECTORS]
        active_slack_nonzero = sum(row.get("slack_nonzero_bytes", 0) for row in active_physical)

    return {
        "kind": "save",
        "file": path.name,
        **hashes(data),
        "slots": slots,
        "active_slot": active_slot,
        "active_slot_slack_nonzero_bytes": active_slack_nonzero,
        "sectors_28_31_all_zero": all(
            not any(data[i * SECTOR_SIZE:(i + 1) * SECTOR_SIZE]) for i in range(28, 32)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit legally obtained Pokémon Ruby ROM/save inputs without modifying them.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    results = []
    for path in args.paths:
        suffix = path.suffix.lower()
        if suffix == ".gba":
            results.append(analyze_rom(path))
        elif suffix == ".sav":
            results.append(analyze_save(path))
        else:
            raise ValueError(f"unsupported input suffix: {path}")

    report = {
        "format": "ruby-rom-save-audit-v1",
        "save_layout": {
            "flash_bytes": TOTAL_FLASH_SECTORS * SECTOR_SIZE,
            "sector_bytes": SECTOR_SIZE,
            "main_slot_sectors": SAVE_SLOT_SECTORS,
            "main_slots": 2,
            "footer_offset": SECTOR_DATA_END,
            "signature": f"{FILE_SIGNATURE:08x}",
            "chunk_sizes": CHUNK_SIZES,
            "sidecar_slack_per_section": [SECTOR_DATA_END - size for size in CHUNK_SIZES],
            "sidecar_slack_per_slot": sum(SECTOR_DATA_END - size for size in CHUNK_SIZES),
        },
        "inputs": results,
    }

    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
