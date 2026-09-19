#!/usr/bin/env python3
"""Audit a pokeruby working tree against the Emerald canonical item manifest."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TYPE_VALUES = {
    "ITEM_USE_MAIL": 0,
    "ITEM_USE_PARTY_MENU": 1,
    "ITEM_USE_FIELD": 2,
    "ITEM_USE_PBLOCK_CASE": 3,
    "ITEM_USE_BAG_MENU": 4,
}
BATTLE_USAGE_VALUES = {
    "ITEM_B_USE_NONE": 0,
    "ITEM_B_USE_MEDICINE": 1,
    "ITEM_B_USE_OTHER": 2,
}
SECONDARY_VALUES = {
    "MACH_BIKE": 0,
    "ACRO_BIKE": 1,
    "OLD_ROD": 0,
    "GOOD_ROD": 1,
    "SUPER_ROD": 2,
}
HOLD_EFFECT_EQUIV = {
    "HOLD_EFFECT_FRIENDSHIP_UP": "27",
    "HOLD_EFFECT_HAPPINESS_UP": "27",
    "HOLD_EFFECT_NONE": "0",
}


def item_blocks(text: str) -> list[str]:
    marker = "const struct Item gItems[]"
    pos = text.index(marker)
    pos = text.index("{", pos)
    depth = 1
    start = None
    out = []
    for i in range(pos + 1, len(text)):
        ch = text[i]
        if ch == "{":
            if depth == 1:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 1 and start is not None:
                out.append(text[start:i + 1])
                start = None
            elif depth == 0:
                return out
    raise ValueError("unterminated gItems array")


def field(block: str, name: str) -> str | None:
    m = re.search(r"(?m)^\s*\." + re.escape(name) + r"\s*=\s*([^,\n}]+)", block)
    return m.group(1).strip() if m else None


def normalize(expr: str | None, kind: str, symbols: dict[str, int]) -> str:
    if expr is None or expr in ("NULL", "FALSE"):
        return "NULL" if kind in ("fieldUseFunc", "battleUseFunc") else "0"
    if expr == "TRUE":
        return "1"
    if kind == "holdEffect" and expr in HOLD_EFFECT_EQUIV:
        return HOLD_EFFECT_EQUIV[expr]
    if expr in TYPE_VALUES:
        return str(TYPE_VALUES[expr])
    if expr in BATTLE_USAGE_VALUES:
        return str(BATTLE_USAGE_VALUES[expr])
    if expr in SECONDARY_VALUES:
        return str(SECONDARY_VALUES[expr])
    if re.fullmatch(r"-?\d+", expr):
        return str(int(expr))
    if re.fullmatch(r"0x[0-9A-Fa-f]+", expr):
        return str(int(expr, 16))

    m = re.fullmatch(r"(ITEM_[A-Z0-9_]+)\s*-\s*FIRST_BALL", expr)
    if m:
        return str(symbols[m.group(1)] - symbols["ITEM_MASTER_BALL"])
    m = re.fullmatch(r"ITEM_TO_MAIL\((ITEM_[A-Z0-9_]+)\)", expr)
    if m:
        return str(symbols[m.group(1)] - symbols["ITEM_ORANGE_MAIL"])

    return expr


def audit_table(path: Path, manifest: dict) -> list[str]:
    blocks = item_blocks(path.read_text(encoding="utf-8"))
    items = manifest["items"]
    if len(blocks) != 377:
        return [f"{path}: gItems count {len(blocks)} != 377"]

    symbols = {x["symbol"]: x["id"] for x in items if x.get("symbol")}
    field_pairs = [
        ("price", "price"),
        ("holdEffect", "holdEffect"),
        ("holdEffectParam", "holdEffectParam"),
        ("importance", "importance"),
        ("exitsBagOnUse", "registrability"),
        ("pocket", "pocket"),
        ("type", "type"),
        ("fieldUseFunc", "fieldUseFunc"),
        ("battleUsage", "battleUsage"),
        ("battleUseFunc", "battleUseFunc"),
        ("secondaryId", "secondaryId"),
    ]
    diffs = []
    for idx, (block, expected) in enumerate(zip(blocks, items)):
        for ruby_field, emerald_field in field_pairs:
            got = normalize(field(block, ruby_field), ruby_field, symbols)
            want = normalize(expected.get(emerald_field), ruby_field, symbols)
            if got != want:
                diffs.append(
                    f"{path}: id {idx} {expected.get('symbol')} {ruby_field}: got {got}, want {want}"
                )
    return diffs


def audit_constants(path: Path, manifest: dict) -> list[str]:
    text = path.read_text(encoding="utf-8")
    diffs = []
    for item in manifest["items"][349:377]:
        pat = rf"(?m)^#define\s+{re.escape(item['symbol'])}\s+{item['id']}\s*$"
        if not re.search(pat, text):
            diffs.append(f"{path}: missing {item['symbol']}={item['id']}")
    if not re.search(r"(?m)^#define\s+ITEMS_COUNT\s+377\s*$", text):
        diffs.append(f"{path}: ITEMS_COUNT != 377")
    return diffs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ruby", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    diffs = []
    diffs += audit_constants(args.ruby / "include/constants/items.h", manifest)
    diffs += audit_table(args.ruby / "src/data/items_en.h", manifest)
    diffs += audit_table(args.ruby / "src/data/items_de.h", manifest)

    if diffs:
        print(f"Emerald item parameter audit: {len(diffs)} mismatches")
        for line in diffs[:200]:
            print(line)
        raise SystemExit(1)

    print("Emerald item parameter audit: 0 mismatches across IDs 0..376 (EN/DE gameplay fields).")


if __name__ == "__main__":
    main()
