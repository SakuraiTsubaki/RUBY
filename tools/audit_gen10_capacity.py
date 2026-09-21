#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def macro(text: str, name: str):
    m = re.search(rf"(?m)^\s*#define\s+{re.escape(name)}\s+([^\s/]+)", text)
    return m.group(1) if m else None


def field_width(text: str, struct_name: str, field: str):
    m = re.search(rf"struct\s+{re.escape(struct_name)}\s*\{{(.*?)\n\}};", text, re.S)
    if not m:
        return None
    body = m.group(1)
    f = re.search(rf"(?m)^\s*(?:/\\*.*?\\*/\s*)?(u8|s8|u16|s16|u32|s32)\s+{re.escape(field)}(?:\[[^\]]+\])?\s*;", body)
    if f:
        return {"u8": 8, "s8": 8, "u16": 16, "s16": 16, "u32": 32, "s32": 32}[f.group(1)]
    enum_field = re.search(rf"(?m)^\s*(?:/\\*.*?\\*/\s*)?enum\s+\w+\s+{re.escape(field)}(?:\[[^\]]+\])?\s*;", body)
    if enum_field:
        return "enum"
    return None


def inspect_classic(root: Path) -> dict:
    species = read(root / "include/constants/species.h")
    moves = read(root / "include/constants/moves.h")
    items = read(root / "include/constants/items.h")
    abilities = read(root / "include/constants/abilities.h")
    pokemon = read(root / "include/pokemon.h")

    return {
        "source": str(root),
        "macros": {
            "NUM_SPECIES": macro(species, "NUM_SPECIES"),
            "NUM_MOVES": macro(moves, "NUM_MOVES"),
            "ITEMS_COUNT": macro(items, "ITEMS_COUNT"),
            "ABILITIES_COUNT": macro(abilities, "ABILITIES_COUNT"),
        },
        "storage_bits": {
            "PokemonSubstruct0.species": field_width(pokemon, "PokemonSubstruct0", "species"),
            "PokemonSubstruct0.heldItem": field_width(pokemon, "PokemonSubstruct0", "heldItem"),
            "BattlePokemon.species": field_width(pokemon, "BattlePokemon", "species"),
            "BattlePokemon.ability": field_width(pokemon, "BattlePokemon", "ability"),
            "BattlePokemon.item": field_width(pokemon, "BattlePokemon", "item"),
        },
        "legacy_box_pokemon_size": "0x50",
        "legacy_alt_ability_bits": 1,
    }


def find_first(root: Path, candidates: list[str]) -> Path | None:
    for rel in candidates:
        p = root / rel
        if p.exists():
            return p
    return None


def inspect_expanded(root: Path) -> dict:
    result = {"source": str(root), "present": root.exists()}
    if not root.exists():
        return result

    files = {
        "species": find_first(root, ["include/constants/species.h"]),
        "moves": find_first(root, ["include/constants/moves.h"]),
        "items": find_first(root, ["include/constants/items.h"]),
        "abilities": find_first(root, ["include/constants/abilities.h"]),
        "pokemon": find_first(root, ["include/pokemon.h"]),
    }
    result["files"] = {k: (str(v.relative_to(root)) if v else None) for k, v in files.items()}

    macros = {}
    for key, name in [
        ("species", "NUM_SPECIES"),
        ("moves", "MOVES_COUNT"),
        ("moves", "NUM_MOVES"),
        ("items", "ITEMS_COUNT"),
        ("abilities", "ABILITIES_COUNT"),
    ]:
        p = files.get(key)
        if p:
            value = macro(read(p), name)
            if value is not None:
                macros[name] = value
    result["macros"] = macros

    if files["pokemon"]:
        text = read(files["pokemon"])
        result["storage_bits"] = {
            "BattlePokemon.species": field_width(text, "BattlePokemon", "species"),
            "BattlePokemon.ability": field_width(text, "BattlePokemon", "ability"),
            "BattlePokemon.item": field_width(text, "BattlePokemon", "item"),
        }

        def packed_bits(field_pattern: str):
            m = re.search(field_pattern, text)
            return int(m.group(1)) if m else None

        result["persistent_packed_bits"] = {
            "species": packed_bits(r"enum\s+Species\s+species:(\d+)"),
            "move": packed_bits(r"enum\s+Move\s+move1:(\d+)"),
            "heldItem": packed_bits(r"enum\s+Item\s+heldItem:(\d+)"),
            "abilityNum": packed_bits(r"abilityNum:(\d+)"),
        }
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--classic", type=Path, required=True)
    ap.add_argument("--expanded", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    report = {
        "policy": "capacity-before-forms",
        "generation_target": 10,
        "targets": {
            "species_id_bits": 16,
            "move_id_bits": 16,
            "item_id_bits": 16,
            "ability_id_bits": 16,
            "dex_number_bits": 16,
            "type_id_bits": 8,
            "form_id_bits_reserved": 16,
        },
        "classic": inspect_classic(args.classic.resolve()),
        "expanded": inspect_expanded(args.expanded.resolve()) if args.expanded else None,
    }

    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
