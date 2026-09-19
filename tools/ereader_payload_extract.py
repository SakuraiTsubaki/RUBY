#!/usr/bin/env python3
"""Decode Pokémon Ruby/Sapphire e-Reader RAW cards and extract event payloads.

No third-party Python packages are required.

The pipeline implemented here is:
    RAW dotcode -> deinterleaved BIN card -> merged application -> VPK0 decode
                 -> payload discovery using pokeruby checksum rules

This tool intentionally does not ship card dumps. Supply your own .raw files.
For multi-strip cards, pass files in scan order.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

LONG_RAW_SIZE = 0xB60
SHORT_RAW_SIZE = 0x750
LONG_TEMP_SIZE = 0xB00
SHORT_TEMP_SIZE = 0x700
LONG_CODE_SIZE = 0x810
SHORT_CODE_SIZE = 0x510
CARD_HEADER_SIZE = 0x30

SIDE_APP = 2
APP_STANDALONE = 0xE
APP_LINKDATA = 0xF
RAW_APP_NAME_LEN = 0x21
RAW_CARD_NAME_LEN = 0x21

ENIGMA_BERRY_SIZE = 0x530
ENIGMA_BERRY_CHECKSUM_OFF = 0x52C
ENIGMA_BERRY_MAX_YIELD_OFF = 0x0A
ENIGMA_BERRY_DESC_PTR1_OFF = 0x0C
ENIGMA_BERRY_DESC_PTR2_END = 0x14
ENIGMA_BERRY_STAGE_DURATION_OFF = 0x14

EREADER_TRAINER_SIZE = 0xBC
EREADER_TRAINER_CHECKSUM_OFF = 0xB8
EREADER_TRAINER_WORDS = EREADER_TRAINER_CHECKSUM_OFF // 4

DECOR_REGIROCK_DOLL = 118
DECOR_REGICE_DOLL = 119
DECOR_REGISTEEL_DOLL = 120

SCRIPT_CMD_ADDDECORATION = 0x4B
SCRIPT_CMD_BUFFERDECORATIONNAME = 0x81


class DecodeError(ValueError):
    pass


@dataclass(frozen=True)
class CardMeta:
    path: str
    region: int
    app_type: int
    card_no: int
    card_count: int
    app_len: int
    code_len: int


class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.byte = 0
        self.bit = 7

    def read(self, bits: int) -> int:
        value = 0
        for _ in range(bits):
            if self.byte >= len(self.data):
                raise DecodeError("unexpected end of VPK0 bitstream")
            value = (value << 1) | ((self.data[self.byte] >> self.bit) & 1)
            self.bit -= 1
            if self.bit < 0:
                self.bit = 7
                self.byte += 1
        return value


def _read_huffman(reader: BitReader):
    tree = []
    while True:
        if reader.read(1):
            if len(tree) >= 2:
                tree[-2] = [tree[-2], tree[-1]]
                tree.pop()
            else:
                return tree[0] if tree else None
        else:
            tree.append(reader.read(8))


def _search_huffman(reader: BitReader, tree) -> int:
    if isinstance(tree, list):
        return _search_huffman(reader, tree[reader.read(1)])
    return tree


def decompress_vpk0(data: bytes) -> bytes:
    reader = BitReader(data)
    if reader.read(32) != 0x76706B30:  # "vpk0"
        raise DecodeError("VPK0 magic not found")

    output_size = reader.read(32)
    method = reader.read(8)
    move_tree = _read_huffman(reader)
    size_tree = _read_huffman(reader)
    out = bytearray()

    while len(out) < output_size:
        if reader.read(1):
            move_bits = _search_huffman(reader, move_tree)
            move = reader.read(move_bits)

            if method:
                if move < 3:
                    second_bits = _search_huffman(reader, move_tree)
                    second = reader.read(second_bits)
                    move = move - 1 + ((second - 2) << 2)
                else:
                    move = (move - 2) << 2

            size_bits = _search_huffman(reader, size_tree)
            size = reader.read(size_bits)

            if move <= 0 or move > len(out):
                raise DecodeError(
                    f"invalid VPK0 back-reference distance {move} at output {len(out)}"
                )

            for _ in range(size):
                out.append(out[-move])
                if len(out) >= output_size:
                    break
        else:
            out.append(reader.read(8))

    return bytes(out[:output_size])


def raw_to_bin(raw: bytes) -> bytes:
    if len(raw) == LONG_RAW_SIZE:
        temp_len = LONG_TEMP_SIZE
        scan_end = 0xB38
        code_len = LONG_CODE_SIZE
    elif len(raw) == SHORT_RAW_SIZE:
        temp_len = SHORT_TEMP_SIZE
        scan_end = 0x724
        code_len = SHORT_CODE_SIZE
    else:
        raise DecodeError(
            f"unsupported RAW size 0x{len(raw):X}; expected "
            f"0x{LONG_RAW_SIZE:X} or 0x{SHORT_RAW_SIZE:X}"
        )

    temp = bytearray(temp_len)
    src = 2
    dst = 0
    while src < scan_end:
        if src % 0x68 == 0:
            src += 2
        temp[dst] = raw[src]
        dst += 1
        src += 1

    card = bytearray(CARD_HEADER_SIZE + code_len)
    interleave = temp_len // 0x40
    for block in range(0, len(card), 0x30):
        block_index = block // 0x30
        for column in range(0x30):
            card[block + column] = temp[column * interleave + block_index]
    return bytes(card)


def _card_fragment(card: bytes, used: int, path: str) -> tuple[bytes, CardMeta]:
    side = card[0x03]
    code_len = int.from_bytes(card[0x06:0x08], "big")
    app_type = card[0x0C] >> 4
    region = card[0x0D] & 0x0F
    card_no = (card[0x26] >> 1) & 0x0F
    card_count = ((card[0x27] & 1) << 3) | (card[0x26] >> 5)
    app_len = (card[0x28] << 7) | (card[0x27] >> 1)

    if side != SIDE_APP or app_type not in (APP_STANDALONE, APP_LINKDATA):
        raise DecodeError(
            f"{path}: expected standalone/link application card, "
            f"got side={side}, app_type=0x{app_type:X}"
        )

    start = CARD_HEADER_SIZE + RAW_APP_NAME_LEN
    if not (card[0x2A] & 0x02):
        start += RAW_CARD_NAME_LEN * card_count

    fragment = card[start:]
    if used >= app_len:
        fragment = b""
    elif used + len(fragment) > app_len:
        fragment = fragment[: app_len - used]

    return fragment, CardMeta(
        path=path,
        region=region,
        app_type=app_type,
        card_no=card_no,
        card_count=card_count,
        app_len=app_len,
        code_len=code_len,
    )


def decode_raw_cards(paths: Sequence[Path]) -> tuple[bytes, list[CardMeta], bytes]:
    if not paths:
        raise DecodeError("at least one RAW card is required")

    merged = bytearray()
    metas: list[CardMeta] = []
    expected_app_len = None
    expected_count = None

    for path in paths:
        card = raw_to_bin(path.read_bytes())
        fragment, meta = _card_fragment(card, len(merged), str(path))
        metas.append(meta)

        if expected_app_len is None:
            expected_app_len = meta.app_len
            expected_count = meta.card_count
        elif meta.app_len != expected_app_len:
            raise DecodeError("multi-strip cards disagree on application length")

        merged.extend(fragment)

    if expected_count and len(paths) != expected_count:
        raise DecodeError(
            f"card set declares {expected_count} strip(s), but {len(paths)} were supplied"
        )
    if expected_app_len is not None and len(merged) != expected_app_len:
        raise DecodeError(
            f"merged application is {len(merged)} bytes, expected {expected_app_len}"
        )

    vpk_at = bytes(merged).find(b"vpk0")
    if vpk_at < 0:
        raise DecodeError("no VPK0 stream found in merged card application")

    decoded = decompress_vpk0(bytes(merged[vpk_at:]))
    return decoded, metas, bytes(merged)


def _u32le(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def find_enigma_berry_payloads(decoded: bytes) -> list[int]:
    hits = []
    for off in range(0, len(decoded) - ENIGMA_BERRY_SIZE + 1):
        if decoded[off + ENIGMA_BERRY_STAGE_DURATION_OFF] == 0:
            continue
        if decoded[off + ENIGMA_BERRY_MAX_YIELD_OFF] == 0:
            continue

        body = bytearray(
            decoded[off : off + ENIGMA_BERRY_CHECKSUM_OFF]
        )
        # pokeruby excludes the two runtime description pointers by nulling them.
        body[
            ENIGMA_BERRY_DESC_PTR1_OFF:ENIGMA_BERRY_DESC_PTR2_END
        ] = b"\0" * (
            ENIGMA_BERRY_DESC_PTR2_END - ENIGMA_BERRY_DESC_PTR1_OFF
        )
        checksum = sum(body) & 0xFFFFFFFF
        stored = _u32le(decoded, off + ENIGMA_BERRY_CHECKSUM_OFF)
        if checksum == stored:
            hits.append(off)
    return hits


def find_ereader_trainer_payloads(decoded: bytes) -> list[int]:
    hits = []
    for off in range(0, len(decoded) - EREADER_TRAINER_SIZE + 1):
        # The additive checksum alone can have accidental matches inside the
        # e-Reader program. Filter candidates with stable R/S trainer structure
        # constraints before accepting the checksum.
        unk0 = decoded[off]
        trainer_class = decoded[off + 1]
        win_streak = int.from_bytes(decoded[off + 2 : off + 4], "little")

        # pokeruby debug code uses trainerClass % 77. Japanese cards observed
        # here use unk0 0 for direct battles, or 50/100 for tower-style cards.
        if unk0 not in (0, 50, 100):
            continue
        if trainer_class >= 77:
            continue
        if win_streak > 100:
            continue

        valid_party = True
        for party_index in range(3):
            mon = off + 0x34 + party_index * 0x2C
            species = int.from_bytes(decoded[mon : mon + 2], "little")
            level = decoded[mon + 0x0C]
            if not (1 <= species <= 411 and 1 <= level <= 100):
                valid_party = False
                break
        if not valid_party:
            continue

        words = [
            _u32le(decoded, off + i * 4)
            for i in range(EREADER_TRAINER_WORDS)
        ]
        if not any(words):
            continue
        checksum = sum(words) & 0xFFFFFFFF
        stored = _u32le(decoded, off + EREADER_TRAINER_CHECKSUM_OFF)
        if checksum == stored:
            hits.append(off)
    return hits


def find_regi_decoration_scripts(decoded: bytes) -> dict[int, list[int]]:
    """Find the O001-style 'buffer name; add decoration' field scripts."""
    hits: dict[int, list[int]] = {}
    for decor_id in (
        DECOR_REGIROCK_DOLL,
        DECOR_REGICE_DOLL,
        DECOR_REGISTEEL_DOLL,
    ):
        pattern = bytes(
            [
                SCRIPT_CMD_BUFFERDECORATIONNAME,
                0x00,  # output string buffer
                decor_id,
                0x00,
                SCRIPT_CMD_ADDDECORATION,
                decor_id,
                0x00,
            ]
        )
        offsets = []
        start = 0
        while True:
            off = decoded.find(pattern, start)
            if off < 0:
                break
            offsets.append(off)
            start = off + 1
        hits[decor_id] = offsets
    return hits


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _metadata(paths: Sequence[Path], decoded: bytes, metas: Sequence[CardMeta]) -> dict:
    return {
        "inputs": [
            {
                "path": str(p),
                "size": p.stat().st_size,
                "sha256": sha256(p.read_bytes()),
            }
            for p in paths
        ],
        "cards": [m.__dict__ for m in metas],
        "decoded": {
            "size": len(decoded),
            "sha256": sha256(decoded),
        },
    }


def command_decode(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.cards]
    decoded, metas, merged = decode_raw_cards(paths)
    Path(args.output).write_bytes(decoded)

    info = _metadata(paths, decoded, metas)
    info["merged_application"] = {
        "size": len(merged),
        "sha256": sha256(merged),
    }
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def _require_one(hits: list[int], kind: str) -> int:
    if len(hits) != 1:
        formatted = ", ".join(f"0x{x:X}" for x in hits) or "none"
        raise DecodeError(
            f"expected exactly one {kind} payload, found {len(hits)}: {formatted}"
        )
    return hits[0]


def command_extract(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.cards]
    decoded, metas, _ = decode_raw_cards(paths)
    info = _metadata(paths, decoded, metas)

    if args.kind == "berry":
        off = _require_one(find_enigma_berry_payloads(decoded), "Enigma Berry")
        payload = decoded[off : off + ENIGMA_BERRY_SIZE]
        Path(args.output).write_bytes(payload)
        info["payload"] = {
            "kind": "enigma_berry",
            "offset": f"0x{off:X}",
            "size": len(payload),
            "sha256": sha256(payload),
            "stored_checksum": f"0x{_u32le(payload, ENIGMA_BERRY_CHECKSUM_OFF):08X}",
        }

    elif args.kind == "trainer":
        off = _require_one(
            find_ereader_trainer_payloads(decoded), "Battle-e trainer"
        )
        payload = decoded[off : off + EREADER_TRAINER_SIZE]
        Path(args.output).write_bytes(payload)
        info["payload"] = {
            "kind": "battle_e_trainer",
            "offset": f"0x{off:X}",
            "size": len(payload),
            "sha256": sha256(payload),
            "stored_checksum": f"0x{_u32le(payload, EREADER_TRAINER_CHECKSUM_OFF):08X}",
        }

    elif args.kind == "decoration":
        hits = find_regi_decoration_scripts(decoded)
        info["payload"] = {
            "kind": "decoration_present",
            "regirock_doll": [f"0x{x:X}" for x in hits[DECOR_REGIROCK_DOLL]],
            "regice_doll": [f"0x{x:X}" for x in hits[DECOR_REGICE_DOLL]],
            "registeel_doll": [f"0x{x:X}" for x in hits[DECOR_REGISTEEL_DOLL]],
        }
        Path(args.output).write_text(
            json.dumps(info["payload"], indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        raise DecodeError(f"unsupported kind: {args.kind}")

    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def command_scan(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.cards]
    decoded, metas, _ = decode_raw_cards(paths)
    info = _metadata(paths, decoded, metas)
    info["hits"] = {
        "enigma_berry": [
            f"0x{x:X}" for x in find_enigma_berry_payloads(decoded)
        ],
        "battle_e_trainer": [
            f"0x{x:X}" for x in find_ereader_trainer_payloads(decoded)
        ],
        "regi_decoration_scripts": {
            str(k): [f"0x{x:X}" for x in v]
            for k, v in find_regi_decoration_scripts(decoded).items()
        },
    }
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Decode Pokémon R/S e-Reader RAW cards without legacy Windows tools."
    )
    sub = p.add_subparsers(dest="command", required=True)

    dec = sub.add_parser("decode", help="decode RAW card set to decompressed app")
    dec.add_argument("cards", nargs="+", help="RAW cards in scan order")
    dec.add_argument("-o", "--output", required=True)
    dec.set_defaults(func=command_decode)

    ext = sub.add_parser("extract", help="extract a verified event payload")
    ext.add_argument("kind", choices=("berry", "trainer", "decoration"))
    ext.add_argument("cards", nargs="+", help="RAW cards in scan order")
    ext.add_argument("-o", "--output", required=True)
    ext.set_defaults(func=command_extract)

    scan = sub.add_parser("scan", help="report recognized payloads without writing them")
    scan.add_argument("cards", nargs="+", help="RAW cards in scan order")
    scan.set_defaults(func=command_scan)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (DecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
