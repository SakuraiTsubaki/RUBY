#!/usr/bin/env python3
"""
Apply Pokémon Emerald item gameplay parameters to a pret/pokeruby working tree.

Localization is intentionally not synchronized here:
- existing Ruby names/descriptions are preserved for IDs 0..348;
- Emerald English names are used only as fallback labels for new IDs 349..376;
- new descriptions use Ruby's dummy description until the localization layer supplies them.

Canonical data: manifests/emerald-item-parameters.json
"""
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
HOLD_EFFECT_ALIASES = {
    # Same numeric Gen III hold effect (27), renamed by pokeemerald.
    "HOLD_EFFECT_FRIENDSHIP_UP": "HOLD_EFFECT_HAPPINESS_UP",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def item_array_blocks(text: str) -> tuple[int, int, list[tuple[int, int, str]]]:
    marker = "const struct Item gItems[]"
    pos = text.index(marker)
    open_pos = text.index("{", pos)
    depth = 1
    start = None
    blocks: list[tuple[int, int, str]] = []
    i = open_pos + 1
    while i < len(text):
        ch = text[i]
        if ch == "{":
            if depth == 1:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 1 and start is not None:
                blocks.append((start, i + 1, text[start:i + 1]))
                start = None
            elif depth == 0:
                return open_pos, i, blocks
        i += 1
    raise ValueError("unterminated gItems array")


def replace_designator(block: str, field: str, value: str) -> str:
    pattern = re.compile(r"(?m)^(\s*)\." + re.escape(field) + r"\s*=\s*[^,\n}]+,")
    m = pattern.search(block)
    if m:
        return block[:m.start()] + f"{m.group(1)}.{field} = {value}," + block[m.end():]

    # Insert before the closing brace, following Ruby's explicit-field style.
    close = block.rfind("}")
    return block[:close] + f"        .{field} = {value},\n    " + block[close:]


def expr_to_int(expr: str | None, field: str, symbol_to_id: dict[str, int]) -> int:
    if not expr or expr in ("NULL", "FALSE"):
        return 0
    if expr == "TRUE":
        return 1
    if expr in TYPE_VALUES:
        return TYPE_VALUES[expr]
    if expr in BATTLE_USAGE_VALUES:
        return BATTLE_USAGE_VALUES[expr]
    if expr in SECONDARY_VALUES:
        return SECONDARY_VALUES[expr]
    if re.fullmatch(r"-?\d+", expr):
        return int(expr)
    if re.fullmatch(r"0x[0-9A-Fa-f]+", expr):
        return int(expr, 16)

    m = re.fullmatch(r"(ITEM_[A-Z0-9_]+)\s*-\s*FIRST_BALL", expr)
    if m:
        return symbol_to_id[m.group(1)] - symbol_to_id["ITEM_MASTER_BALL"]

    m = re.fullmatch(r"ITEM_TO_MAIL\((ITEM_[A-Z0-9_]+)\)", expr)
    if m:
        return symbol_to_id[m.group(1)] - symbol_to_id["ITEM_ORANGE_MAIL"]

    raise ValueError(f"cannot normalize {field}: {expr}")


def gameplay_values(item: dict, symbol_to_id: dict[str, int]) -> dict[str, str]:
    hold = item.get("holdEffect") or "0"
    hold = HOLD_EFFECT_ALIASES.get(hold, hold)
    return {
        "price": str(expr_to_int(item.get("price"), "price", symbol_to_id)),
        "holdEffect": hold if hold.startswith("HOLD_EFFECT_") else str(expr_to_int(hold, "holdEffect", symbol_to_id)),
        "holdEffectParam": str(expr_to_int(item.get("holdEffectParam"), "holdEffectParam", symbol_to_id)),
        "importance": str(expr_to_int(item.get("importance"), "importance", symbol_to_id)),
        # Ruby's byte at this exact struct offset is named exitsBagOnUse.
        # Emerald names the same byte registrability. Both are unused in vanilla.
        "exitsBagOnUse": str(expr_to_int(item.get("registrability"), "registrability", symbol_to_id)),
        "pocket": item.get("pocket") or "0",
        "type": str(expr_to_int(item.get("type"), "type", symbol_to_id)),
        "fieldUseFunc": item.get("fieldUseFunc") or "NULL",
        "battleUsage": str(expr_to_int(item.get("battleUsage"), "battleUsage", symbol_to_id)),
        "battleUseFunc": item.get("battleUseFunc") or "NULL",
        "secondaryId": str(expr_to_int(item.get("secondaryId"), "secondaryId", symbol_to_id)),
    }


def sync_constants(path: Path, items: list[dict]) -> None:
    text = read(path)
    if "#define ITEMS_COUNT 377" in text:
        return

    anchor = "#define ITEM_15C 348\n\n#define ITEMS_COUNT 349"
    if anchor not in text:
        raise ValueError("unexpected pokeruby item constant tail")

    extra = []
    for item in items[349:377]:
        extra.append(f"#define {item['symbol']} {item['id']}")
    replacement = "#define ITEM_15C 348\n\n" + "\n".join(extra) + "\n\n#define ITEMS_COUNT 377"
    write(path, text.replace(anchor, replacement, 1))


def render_new_item(item: dict, symbol_to_id: dict[str, int]) -> str:
    v = gameplay_values(item, symbol_to_id)
    name = item.get("name") or "????????"
    return f'''    {{
        .name = _("{name}"),
        .itemId = {item["symbol"]},
        .price = {v["price"]},
        .holdEffect = {v["holdEffect"]},
        .holdEffectParam = {v["holdEffectParam"]},
        .description = gItemDescription_Dummy,
        .importance = {v["importance"]},
        .exitsBagOnUse = {v["exitsBagOnUse"]},
        .pocket = {v["pocket"]},
        .type = {v["type"]},
        .fieldUseFunc = {v["fieldUseFunc"]},
        .battleUsage = {v["battleUsage"]},
        .battleUseFunc = {v["battleUseFunc"]},
        .secondaryId = {v["secondaryId"]},
    }}'''


def sync_item_table(path: Path, items: list[dict], symbol_to_id: dict[str, int]) -> None:
    text = read(path)
    _, close_pos, blocks = item_array_blocks(text)
    if len(blocks) not in (349, 377):
        raise ValueError(f"{path}: expected 349 or 377 gItems entries, got {len(blocks)}")

    # Rewrite existing Ruby entries by positional ID, preserving language text.
    replacements = []
    for idx in range(min(349, len(blocks))):
        start, end, block = blocks[idx]
        v = gameplay_values(items[idx], symbol_to_id)
        changed = False
        for field, value in v.items():
            current_match = re.search(
                r"(?m)^\\s*\\." + re.escape(field) + r"\\s*=\\s*([^,\\n}]+)",
                block,
            )
            current = current_match.group(1).strip() if current_match else None

            # Preserve Ruby's spelling when it is numerically/semantically
            # equivalent to Emerald. This keeps the generated patch focused
            # on real parameter differences rather than cosmetic rewrites.
            equivalent = current == value
            if field == "holdEffect" and value == "0" and current == "HOLD_EFFECT_NONE":
                equivalent = True
            if field == "holdEffect" and value == "HOLD_EFFECT_HAPPINESS_UP" and current == "HOLD_EFFECT_HAPPINESS_UP":
                equivalent = True
            if current is None and value in ("0", "NULL"):
                equivalent = True

            if not equivalent:
                block = replace_designator(block, field, value)
                changed = True
        if changed:
            replacements.append((start, end, block))

    for start, end, block in reversed(replacements):
        text = text[:start] + block + text[end:]

    # Append Emerald's 349..376 range exactly once.
    _, close_pos, blocks = item_array_blocks(text)
    if len(blocks) == 349:
        addition = "\n" + ",\n".join(render_new_item(x, symbol_to_id) for x in items[349:377]) + ",\n"
        text = text[:close_pos] + addition + text[close_pos:]

    write(path, text)


def add_item_use_compat(path: Path) -> None:
    text = read(path)
    if "void ItemUseOutOfBattle_ReduceEV(u8);" not in text:
        text = text.replace(
            "void ItemUseOutOfBattle_Medicine(u8);",
            "void ItemUseOutOfBattle_Medicine(u8);\nvoid ItemUseOutOfBattle_ReduceEV(u8);\nvoid ItemUseOutOfBattle_PowderJar(u8);",
            1,
        )
    write(path, text)


def add_item_use_functions(path: Path) -> None:
    text = read(path)
    if "void ItemUseOutOfBattle_ReduceEV(u8 taskId)" not in text:
        needle = '''void ItemUseOutOfBattle_Medicine(u8 taskId)
{
    gPokemonItemUseCallback = UseMedicine;
    SetPokemonItemUseAndFadeOut(taskId);
}
'''
        replacement = needle + '''
void ItemUseOutOfBattle_ReduceEV(u8 taskId)
{
    // Emerald routes the six EV-lowering friendship berries through the
    // party-menu item path. Ruby's callback ABI is older, so use its generic
    // table-based medicine callback; the signed EV behavior is ported below.
    gPokemonItemUseCallback = UseMedicine;
    SetPokemonItemUseAndFadeOut(taskId);
}

void ItemUseOutOfBattle_PowderJar(u8 taskId)
{
    // Parameter-compatible placeholder. Exact Emerald behavior depends on
    // Berry Crush/Berry Powder save data that Ruby does not contain.
    ItemUseOutOfBattle_CannotUse(taskId);
}
'''
        if needle not in text:
            raise ValueError("Medicine item-use function anchor not found")
        text = text.replace(needle, replacement, 1)
    write(path, text)


def sync_ev_berry_effects(path: Path) -> None:
    text = read(path)
    if "gItemEffect_PomegBerry" not in text:
        anchor = 'const u8 gItemEffect_SitrusBerry[]  = {0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 30};'
        addition = anchor + '''
const u8 gItemEffect_PomegBerry[]   = {0x00, 0x00, 0x00, 0x00, 0x01, 0xe0, 0xf6, 10, 5, 2};
const u8 gItemEffect_KelpsyBerry[]  = {0x00, 0x00, 0x00, 0x00, 0x02, 0xe0, 0xf6, 10, 5, 2};
const u8 gItemEffect_QualotBerry[]  = {0x00, 0x00, 0x00, 0x00, 0x00, 0xe1, 0xf6, 10, 5, 2};
const u8 gItemEffect_HondewBerry[]  = {0x00, 0x00, 0x00, 0x00, 0x00, 0xe8, 0xf6, 10, 5, 2};
const u8 gItemEffect_GrepaBerry[]   = {0x00, 0x00, 0x00, 0x00, 0x00, 0xe4, 0xf6, 10, 5, 2};
const u8 gItemEffect_TamatoBerry[]  = {0x00, 0x00, 0x00, 0x00, 0x00, 0xe2, 0xf6, 10, 5, 2};'''
        if anchor not in text:
            raise ValueError("Sitrus Berry effect anchor not found")
        text = text.replace(anchor, addition, 1)

    # Ruby's table is positional from ITEM_POTION. Patch the six slots by index.
    m = re.search(r"const u8 \*const gItemEffectTable\[\]\s*=\s*\{(.*?)\n\};", text, re.S)
    if not m:
        raise ValueError("gItemEffectTable not found")
    body = m.group(1)
    entries = [x.strip() for x in body.split(",")]
    target = {
        153: "gItemEffect_PomegBerry",
        154: "gItemEffect_KelpsyBerry",
        155: "gItemEffect_QualotBerry",
        156: "gItemEffect_HondewBerry",
        157: "gItemEffect_GrepaBerry",
        158: "gItemEffect_TamatoBerry",
    }
    for item_id, symbol in target.items():
        entries[item_id - 13] = symbol
    new_body = "\n" + "\n".join(f"    {x}," for x in entries if x)[:-1]
    text = text[:m.start(1)] + new_body + text[m.end(1):]
    write(path, text)


def port_signed_ev_logic(path: Path) -> None:
    text = read(path)
    text = text.replace("    u32 evChange;\n", "    s8 evChange;\n    bool8 friendshipOnly = FALSE;\n", 1)

    old_a = '''                        evCount = GetMonEVCount(pkmn);
                        if (evCount >= 510)
                            return TRUE;
                        data = GetMonData(pkmn, sGetMonDataEVConstants[data2], NULL);
                        if (data < 100)
                        {
                            if (data + itemEffect[paramIdx] > 100)
                                evChange = 100 - (data + itemEffect[paramIdx]) + itemEffect[paramIdx];
                            else
                                evChange = itemEffect[paramIdx];
                            if (evCount + evChange > 510)
                                evChange += 510 - (evCount + evChange);
                            data += evChange;
                            SetMonData(pkmn, sGetMonDataEVConstants[data2], &data);
                            CalculateMonStats(pkmn);
                            paramIdx++;
                            retVal = FALSE;
                        }
                        break;'''
    new_a = '''                        evCount = GetMonEVCount(pkmn);
                        data = GetMonData(pkmn, sGetMonDataEVConstants[data2], NULL);
                        evChange = (s8)itemEffect[paramIdx];

                        if (evChange > 0)
                        {
                            if (evCount >= 510)
                                return TRUE;
                            if (data >= 100)
                                break;
                            if (data + evChange > 100)
                                evChange = 100 - data;
                            if (evCount + evChange > 510)
                                evChange = 510 - evCount;
                            data += evChange;
                        }
                        else
                        {
                            if (data == 0)
                            {
                                friendshipOnly = TRUE;
                                paramIdx++;
                                break;
                            }
                            if ((s32)data + evChange < 0)
                                data = 0;
                            else
                                data += evChange;
                        }

                        SetMonData(pkmn, sGetMonDataEVConstants[data2], &data);
                        CalculateMonStats(pkmn);
                        paramIdx++;
                        retVal = FALSE;
                        break;'''
    count = text.count(old_a)
    if count != 1:
        raise ValueError(f"expected one HP/ATK EV block, found {count}")
    text = text.replace(old_a, new_a, 1)

    old_b = '''                        evCount = GetMonEVCount(pkmn);
                        if (evCount >= 510)
                            return TRUE;
                        data = GetMonData(pkmn, sGetMonDataEVConstants[data2 + 2], NULL);
                        if (data < 100)
                        {
                            if (data + itemEffect[paramIdx] > 100)
                                evChange = 100 - (data + itemEffect[paramIdx]) + itemEffect[paramIdx];
                            else
                                evChange = itemEffect[paramIdx];
                            if (evCount + evChange > 510)
                                evChange += 510 - (evCount + evChange);
                            data += evChange;
                            SetMonData(pkmn, sGetMonDataEVConstants[data2 + 2], &data);
                            CalculateMonStats(pkmn);
                            retVal = FALSE;
                            paramIdx++;
                        }
                        break;'''
    new_b = '''                        evCount = GetMonEVCount(pkmn);
                        data = GetMonData(pkmn, sGetMonDataEVConstants[data2 + 2], NULL);
                        evChange = (s8)itemEffect[paramIdx];

                        if (evChange > 0)
                        {
                            if (evCount >= 510)
                                return TRUE;
                            if (data >= 100)
                                break;
                            if (data + evChange > 100)
                                evChange = 100 - data;
                            if (evCount + evChange > 510)
                                evChange = 510 - evCount;
                            data += evChange;
                        }
                        else
                        {
                            if (data == 0)
                            {
                                friendshipOnly = TRUE;
                                paramIdx++;
                                break;
                            }
                            if ((s32)data + evChange < 0)
                                data = 0;
                            else
                                data += evChange;
                        }

                        SetMonData(pkmn, sGetMonDataEVConstants[data2 + 2], &data);
                        CalculateMonStats(pkmn);
                        retVal = FALSE;
                        paramIdx++;
                        break;'''
    count = text.count(old_b)
    if count != 1:
        raise ValueError(f"expected one DEF/etc EV block, found {count}")
    text = text.replace(old_b, new_b, 1)

    # Emerald permits friendship-only use when the target EV is already zero.
    text = text.replace("&& retVal == 0 &&\n                            friendshipMod == 0)",
                        "&& (retVal == 0 || friendshipOnly) &&\n                            friendshipMod == 0)")
    write(path, text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ruby", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    args = ap.parse_args()

    doc = json.loads(read(args.manifest))
    items = doc["items"]
    if len(items) != 377 or items[-1]["id"] != 376:
        raise ValueError("manifest is not the Emerald 0..376 item table")
    symbol_to_id = {x["symbol"]: x["id"] for x in items if x.get("symbol")}

    sync_constants(args.ruby / "include/constants/items.h", items)
    sync_item_table(args.ruby / "src/data/items_en.h", items, symbol_to_id)
    sync_item_table(args.ruby / "src/data/items_de.h", items, symbol_to_id)
    add_item_use_compat(args.ruby / "include/item_use.h")
    add_item_use_functions(args.ruby / "src/item_use.c")
    sync_ev_berry_effects(args.ruby / "src/data/pokemon/item_effects.h")
    port_signed_ev_logic(args.ruby / "src/pokemon_item_effect.c")

    print("Applied Emerald canonical item gameplay parameters (IDs 0..376).")
    print("Note: Powder Jar retains an explicit compatibility stub until Berry Powder/Berry Crush save data is ported.")


if __name__ == "__main__":
    main()
