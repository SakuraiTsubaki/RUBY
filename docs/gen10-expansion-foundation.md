# Generation X Expansion Foundation

## Decision

RUBY expands capacity **before** implementing additional form-change behavior.

Form changes are explicitly deferred until the core engine can represent future species, moves, items, abilities, Pokédex numbers, save metadata, and battle data without Generation III-era width or table limits.

## Engine profiles

### classic

- Source: `pret/pokeruby`
- Pinned baseline: `63a8cbf0016b351a4e68f7036fa0b77e23d2f2c1`
- Responsibility:
  - original Ruby behavior and save compatibility;
  - external-event patches;
  - regression comparison;
  - migration source format.

### expanded

- Source: `rh-hideout/pokeemerald-expansion`
- Pinned reference: `75b806a3ab57a81ff1eb6179288981f0b3cc3050`
- Responsibility:
  - modern battle/data-engine donor;
  - current-generation mechanics reference;
  - capacity architecture for a Ruby content port;
  - future Generation X additions without another structural rewrite.

The expanded profile does **not** yet mean that Ruby maps/story are fully running on the expansion engine. Ruby content migration is a separate implementation layer.

### Important donor limit

The pinned expansion engine is modern in mechanics, but its persistent Pokémon record is still aggressively bit-packed:

- species: 11 bits (0..2047);
- each move: 11 bits (0..2047);
- held item: 10 bits (0..1023);
- ability slot: 2 bits.

Its runtime `BattlePokemon` uses enum-based species/move/item/ability fields and its species data already supports three ability slots, but the packed `BoxPokemon` representation remains the hard persistence boundary.

Therefore the first expanded-profile engineering milestone is **not form support**. It is a versioned persistent-record extension that removes those 11/11/10-bit content ceilings while retaining deterministic migration from classic Ruby saves.

## Current Ruby capacity facts

The pinned classic Ruby baseline currently stores:

- species IDs as `u16`;
- held-item IDs as `u16`;
- move IDs as `u16`;
- battle-mon ability IDs as `u8`;
- two ability choices through the legacy `altAbility` bit;
- `BoxPokemon` as the fixed encrypted 0x50-byte Generation III record.

The baseline constants are Generation III-sized:

- `NUM_SPECIES = SPECIES_EGG` with the Ruby internal species range ending at the Gen III/Unown layout;
- `NUM_MOVES = 355`;
- `ITEMS_COUNT = 349` before the existing Emerald-item synchronization layer;
- `ABILITIES_COUNT = 78`.

Species, move, and item numeric storage already have 16-bit room, but table sizing, Pokédex mappings, save metadata, ability representation, scripts, UI, link buffers, and hard-coded loops still assume the old content model.

## Generation X capacity contract

The expanded Ruby architecture reserves these widths:

| Domain | Required representation |
| --- | --- |
| Species ID | 16-bit |
| Move ID | 16-bit |
| Item ID | 16-bit |
| Ability ID | 16-bit |
| National/other Dex number | 16-bit |
| Type ID | 8-bit |
| Generation ID | 8-bit |
| Form ID | 16-bit reserved only; behavior deferred |

The goal is not to pre-invent Generation X content. The goal is to ensure that adding official Generation X data later is a data/content update rather than another save-structure and battle-ABI rewrite.

## Save strategy

Direct ROM/save inspection is now part of the design baseline; see `docs/ruby-rom-save-expansion.md` and `manifests/ruby-rom-save-baseline.json`.

The supplied Ruby saves verify **6,200 bytes per rotating main slot** between the logical chunk ends and the vanilla footer at `0xFF4`. Those bytes are outside the original per-chunk checksum. Sidecar v1 uses `0x1800` (6,144) bytes of that verified space and leaves 56 bytes unused.

`patches/pokeruby/gen10-save-extension.patch` already implements the first transport layer: version/header, CRC16, read/write across the 14 logical sections, 428 extended-mon records, and global extension storage. Form ID storage is reserved, but form-change behavior remains deferred.

Do **not** enlarge or reinterpret the legacy 0x50-byte `BoxPokemon` record in-place without a migration boundary.

The compatibility rule is:

1. keep the classic Generation III record readable;
2. introduce versioned extended Pokémon metadata outside the legacy encrypted payload, or introduce an explicit v2 record with migration;
3. move modern-only state there, including ability-slot/hidden-ability state and future metadata;
4. migrate party, PC, daycare, trade, battle-tower, record-mixing, and link representations together;
5. verify old saves before enabling writes in the new format.

This avoids silently breaking existing Ruby saves while still allowing the expanded profile to grow.

## Implementation order

1. **Capacity audit**
   - inventory every species/move/item/ability/dex width and hard-coded count;
   - inventory save, link, party, storage, daycare, trainer, contest, and battle structures.

2. **ID/type normalization**
   - introduce project-wide typedefs or equivalent canonical ID types;
   - widen ability-bearing runtime structures from 8-bit assumptions;
   - remove count-dependent random masks and magic constants.

3. **Table decoupling**
   - make all major tables count-driven;
   - remove positional assumptions that depend on Gen III terminal IDs;
   - add compile-time/static validation where the toolchain permits it.

4. **Save sidecar layer**
   - sidecar-v1 transport is implemented in `patches/pokeruby/gen10-save-extension.patch`;
   - preserve legacy reads and vanilla checksum regions;
   - wire the 428 extended-mon records into party, PC, daycare and link copy/move paths;
   - add deterministic migration and downgrade-loss tests.

5. **Expanded engine integration**
   - use the pinned expansion engine as the modern mechanics/data reference;
   - port Ruby-specific maps, scripts, story, event behavior, and assets as a separate layer.

6. **Content population through Generation IX**
   - populate currently known official data after the architecture is stable.

7. **Generation X intake**
   - add official Generation X data when available without changing the core ID/save architecture.

8. **Form-change implementation**
   - only after the capacity/save/battle foundations are stable.

## Non-goals for this phase

- no new form-change runtime;
- no form-specific battle transitions;
- no speculative Generation X species or mechanics;
- no ROM binaries in Git.

## Verification

`tools/audit_gen10_capacity.py` records the current classic and expanded capacity surfaces. CI keeps this inventory reproducible so later patches can prove which Generation III limits have actually been removed.


## Canonical ID type layer

`patches/pokeruby/gen10-id-types.patch` introduces a single capacity contract for expanded Ruby code: 16-bit species, move, item, ability, Pokédex, and reserved form IDs, plus 8-bit type and generation IDs. These typedefs do not alter the legacy encrypted `BoxPokemon` layout by themselves; they are the migration target for runtime APIs and expanded data tables so width changes are explicit instead of being scattered as raw integer types.


## Level-up move ID width

Classic Ruby packs each level-up entry into one 16-bit value: 9 bits for the move and 7 bits for the level. That caps level-up move IDs at 511 even though Pokémon move slots themselves are 16-bit. `patches/pokeruby/gen10-level-up-move-ids.patch` replaces the packed word with a two-word `[move:u16, level:u16]` entry while retaining the existing `const u16[]` learnset declarations. The learning, reminder/tutor, and initial-moveset readers use explicit accessors instead of `0x1FF`/`0xFE00` masks. This removes the 9-bit learnset bottleneck without changing the legacy BoxPokemon save ABI.


## Random move selection

Classic Ruby's random move selector masks `Random()` with `0x1FF`, limiting selection to the legacy 9-bit move range even if `NUM_MOVES` grows. `patches/pokeruby/gen10-random-move-ids.patch` selects uniformly from the configured `NUM_MOVES - 1` nonzero IDs instead, then preserves the existing forbidden-move filtering. Coordinate/graphics uses of `0x1FF` are unrelated and remain unchanged.


## Easy Chat compatibility boundary

Classic Easy Chat encodes a group plus species/move/word index into one `u16`, with a 9-bit index (`0x1FF`). That is a separate compatibility boundary from battle move storage and level-up learnsets. It is now tracked by the capacity audit. Expanding it requires a versioned representation for saved Easy Chat phrases and related Battle Tower/trade text data; the project will not silently widen those saved words and break legacy saves.


## TM/HM compatibility capacity

Classic Ruby stores TM/HM compatibility as exactly two `u32` words per species, capping the table at 64 machine slots. `patches/pokeruby/gen10-tmhm-capacity.patch` derives the row width as `ceil((NUM_TECHNICAL_MACHINES + NUM_HIDDEN_MACHINES) / 32)`, widens the machine index accepted by `CanMonLearnTMHM` to 16 bits, and indexes the compatibility word generically. Existing 58-slot Ruby data remains byte-equivalent in meaning; future tables may populate additional words without another runtime rewrite.
