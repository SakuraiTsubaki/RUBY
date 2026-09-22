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


WIDTHS = {"u8": 8, "s8": 8, "u16": 16, "s16": 16, "u32": 32, "s32": 32}


def field_width(text: str, struct_name: str, field: str):
    m = re.search(rf"struct\s+{re.escape(struct_name)}\s*\{{(.*?)\n\}};", text, re.S)
    if not m:
        return None
    body = m.group(1)
    f = re.search(rf"(?m)^\s*(?:/\\*.*?\\*/\s*)?(u8|s8|u16|s16|u32|s32)\s+{re.escape(field)}(?:\[[^\]]+\])?\s*;", body)
    if f:
        return WIDTHS[f.group(1)]
    enum_field = re.search(rf"(?m)^\s*(?:/\\*.*?\\*/\s*)?enum\s+\w+\s+{re.escape(field)}(?:\[[^\]]+\])?\s*;", body)
    if enum_field:
        return "enum"
    return None


def bitfield_width(text: str, struct_name: str, field: str):
    m = re.search(rf"struct\s+(?:__attribute__\(\(packed\)\)\s+)?{re.escape(struct_name)}\s*\{{(.*?)\n\}};", text, re.S)
    if not m:
        return None
    f = re.search(rf"(?m)^\s*(?:u8|s8|u16|s16|u32|s32)\s+{re.escape(field)}:(\d+)\s*;", m.group(1))
    return int(f.group(1)) if f else None


def function_return_width(text: str, name: str):
    m = re.search(rf"(?m)^\s*(u8|s8|u16|s16|u32|s32)\s+{re.escape(name)}\s*\(", text)
    return WIDTHS[m.group(1)] if m else None


def function_arg_width(text: str, name: str, arg: str):
    m = re.search(rf"(?m)^\s*(?:u8|s8|u16|s16|u32|s32|void)\s+{re.escape(name)}\s*\(([^;{{]]*)\)", text)
    if not m:
        m = re.search(rf"(?m)^\s*(?:u8|s8|u16|s16|u32|s32|void)\s+{re.escape(name)}\s*\(([^)]*)\)", text)
    if not m:
        return None
    f = re.search(rf"\b(u8|s8|u16|s16|u32|s32)\s+{re.escape(arg)}\b", m.group(1))
    return WIDTHS[f.group(1)] if f else None


def inspect_classic(root: Path) -> dict:
    species = read(root / "include/constants/species.h")
    moves = read(root / "include/constants/moves.h")
    items = read(root / "include/constants/items.h")
    abilities = read(root / "include/constants/abilities.h")
    pokemon = read(root / "include/pokemon.h")
    battle = read(root / "include/battle.h")
    battle_message = read(root / "include/battle_message.h")
    pokemon_1 = read(root / "src/pokemon_1.c")
    pokemon_3 = read(root / "src/pokemon_3.c")
    easy_chat = read(root / "include/constants/easy_chat.h")
    easy_chat_2 = read(root / "src/easy_chat_2.c")

    storage_bits = {
        "PokemonSubstruct0.species": field_width(pokemon, "PokemonSubstruct0", "species"),
        "PokemonSubstruct0.heldItem": field_width(pokemon, "PokemonSubstruct0", "heldItem"),
        "BaseStats.ability1": field_width(pokemon, "BaseStats", "ability1"),
        "BaseStats.ability2": field_width(pokemon, "BaseStats", "ability2"),
        "BattlePokemon.species": field_width(pokemon, "BattlePokemon", "species"),
        "BattlePokemon.ability": field_width(pokemon, "BattlePokemon", "ability"),
        "BattlePokemon.item": field_width(pokemon, "BattlePokemon", "item"),
        "StringInfoBattle.lastAbility": field_width(battle_message, "StringInfoBattle", "lastAbility"),
        "StringInfoBattle.abilities": field_width(battle_message, "StringInfoBattle", "abilities"),
        "BattleStruct.abilityPreventingSwitchout": field_width(battle, "BattleStruct", "abilityPreventingSwitchout"),
    }
    function_widths = {
        "GetAbilityBySpecies.return": function_return_width(pokemon, "GetAbilityBySpecies"),
        "GetMonAbility.return": function_return_width(pokemon, "GetMonAbility"),
        "AbilityBattleEffects.ability_arg": function_arg_width(battle, "AbilityBattleEffects", "ability"),
    }
    learnset_packing = {
        "LevelUpMove.move": bitfield_width(pokemon, "LevelUpMove", "move"),
        "LevelUpMove.level": bitfield_width(pokemon, "LevelUpMove", "level"),
        "0x1FF_mask_refs": pokemon_1.count("gLevelUpLearnsets") and pokemon_1.count("0x1FF") + pokemon_3.count("0x1FF"),
        "0xFE00_mask_refs": pokemon_1.count("0xFE00") + pokemon_3.count("0xFE00"),
    }
    ec_shift = re.search(r"#define\s+EC_GROUP\(word\)\s+\(\(word\)\s*>>\s*(\d+)\)", easy_chat)
    ec_mask = re.search(r"#define\s+EC_INDEX\(word\).*?0x([0-9A-Fa-f]+)", easy_chat)
    easy_chat_packing = {
        "group_shift_bits": int(ec_shift.group(1)) if ec_shift else None,
        "index_mask": f"0x{ec_mask.group(1).upper()}" if ec_mask else None,
        "index_bits": int(ec_mask.group(1), 16).bit_length() if ec_mask else None,
        "runtime_0x1FF_refs": easy_chat_2.count("0x1FF"),
    }
    tmhm_table = read(root / "src/data/pokemon/tmhm_learnsets.h")
    tmhm_words = re.search(r"gTMHMLearnsets\[\]\[(\d+)\]", tmhm_table)
    tmhm_capacity = {
        "technical_machines": macro(items, "NUM_TECHNICAL_MACHINES"),
        "hidden_machines": macro(items, "NUM_HIDDEN_MACHINES"),
        "table_words": int(tmhm_words.group(1)) if tmhm_words else None,
        "CanMonLearnTMHM.tm_arg_bits": function_arg_width(pokemon_3, "CanMonLearnTMHM", "tm"),
    }

    return {
        "source": str(root),
        "macros": {
            "NUM_SPECIES": macro(species, "NUM_SPECIES"),
            "NUM_MOVES": macro(moves, "NUM_MOVES"),
            "ITEMS_COUNT": macro(items, "ITEMS_COUNT"),
            "ABILITIES_COUNT": macro(abilities, "ABILITIES_COUNT"),
        },
        "storage_bits": storage_bits,
        "function_widths": function_widths,
        "level_up_learnset_packing": learnset_packing,
        "move_id_blockers": [
            "LevelUpMove.move:9",
            "gLevelUpLearnsets 0x1FF/0xFE00 packing",
        ],
        "easy_chat_packing": easy_chat_packing,
        "easy_chat_id_blockers": [
            "EC move/species index:9",
            "u16 group/index word",
        ],
        "tmhm_capacity": tmhm_capacity,
        "tmhm_blockers": [
            "gTMHMLearnsets[][2]:64 slots",
            "CanMonLearnTMHM tm index:u8",
        ],
        "ability_8bit_blockers": sorted(
            [name for name, width in storage_bits.items() if "ability" in name.lower() and width == 8]
            + [name for name, width in function_widths.items() if "ability" in name.lower() and width == 8]
        ),
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
