# Emerald-canonical item gameplay parameters

## Rule

All item gameplay parameters in the RUBY project use **Pokémon Emerald** as the canonical Gen III reference.

This applies to the complete Emerald item ID range **0–376** (`ITEMS_COUNT = 377`), not only to event tickets.

Canonical source:

- `pret/pokeemerald`
- commit: `5eff78649e7170a877b961ef0b3da13b81a16038`
- item IDs: `include/constants/items.h`
- item table: `src/data/items.h`

Ruby baseline used for synchronization:

- `pret/pokeruby`
- commit: `63a8cbf0016b351a4e68f7036fa0b77e23d2f2c1`

## Gameplay fields

The Emerald values are authoritative for:

- item ID/order
- price
- hold effect
- hold-effect parameter
- importance
- the struct byte named `registrability` in Emerald / `exitsBagOnUse` in Ruby
- pocket
- use type
- field-use function
- battle-use classification
- battle-use function
- secondary ID
- table-driven Pokémon item effects when required by the item

Names and descriptions are **localization data**, not gameplay parameter authority. They are handled separately under the project language order: Japanese first, Korean second when available, English fallback, then other official languages.

## Ruby-to-Emerald synchronization

IDs 0–348 already share the same Gen III ordering. After semantic normalization, the meaningful `gItems` gameplay differences are the six EV-lowering friendship berries:

- Pomeg Berry
- Kelpsy Berry
- Qualot Berry
- Hondew Berry
- Grepa Berry
- Tamato Berry

Emerald routes these through the party-menu EV-reduction path. The synchronization tool also adds Emerald's signed EV-reduction effect data so `-10 EV` is treated as a decrease rather than an unsigned increase.

IDs 349–376 are appended in exact Emerald order, including:

- MysticTicket = 370
- AuroraTicket = 371
- Powder Jar = 372
- Magma Emblem = 375
- Old Sea Map = 376

Eon Ticket remains its canonical Emerald/Ruby ID **275**.

The event courier's visible menu order is intentionally independent of internal item ID order:

1. Eon Ticket
2. Aurora Ticket
3. Mystic Ticket
4. Old Sea Map

## Automation

Canonical data is stored in:

- `manifests/emerald-item-parameters.json`

Application:

    python3 tools/apply_emerald_item_parameters.py \
      --ruby /path/to/pokeruby \
      --manifest manifests/emerald-item-parameters.json

Audit:

    python3 tools/audit_emerald_item_parameters.py \
      --ruby /path/to/pokeruby \
      --manifest manifests/emerald-item-parameters.json

The audit compares gameplay fields for every ID 0–376 in both the English and German pokeruby tables after synchronization.

## Engine dependencies

Exact table parameters do not automatically provide subsystems that Ruby never shipped.

- The six EV-lowering berries require the Emerald signed-EV behavior. This is included in the synchronization tool.
- Powder Jar points to the Emerald Powder Jar use path, but exact behavior depends on the Berry Powder / Berry Crush save subsystem, which Ruby does not contain. The current sync supplies an explicit compatibility function so the table remains buildable; full Berry Powder behavior is a separate engine port.

No ROM binary belongs in this repository. Source transformations, patches, manifests, verification logs, and checksums are the tracked artifacts.
