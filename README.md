# RUBY

Pokémon Ruby modernization and expansion workspace.

## Project direction

RUBY preserves the original Ruby game/story identity while removing legacy external dependencies and building a modern-capacity engine path.

**Current priority: capacity before forms.**

- Form-change implementation is deferred.
- The engine foundation is being prepared for official content through Generation IX and for future Generation X data.
- No speculative Generation X Pokémon, forms, moves, abilities, or mechanics are invented.
- Japanese material is the primary reference; Korean follows when applicable, then English, then other official languages.

## Engine profiles

### Classic Ruby

- Upstream: `pret/pokeruby`
- Pinned baseline: `63a8cbf0016b351a4e68f7036fa0b77e23d2f2c1`
- Purpose:
  - original Ruby behavior and legacy-save verification;
  - Ruby-specific event work;
  - regression reference;
  - migration source format.

### Expanded Ruby foundation

- Modern engine reference: `rh-hideout/pokeemerald-expansion`
- Pinned reference: `75b806a3ab57a81ff1eb6179288981f0b3cc3050`
- Purpose:
  - modern battle/data-engine donor;
  - remove Generation III capacity assumptions;
  - provide a stable architecture that can accept future Generation X data without another core-format rewrite.

The expanded profile is currently a foundation/reference profile. Ruby maps, story, scripts, events, and assets are not yet claimed to be fully ported to that engine.

See:

- `docs/gen10-expansion-foundation.md`
- `manifests/engine-base.yml`
- `tools/audit_gen10_capacity.py`
- `.github/workflows/gen10-capacity-audit.yml`
- `docs/ruby-rom-save-expansion.md`
- `manifests/ruby-rom-save-baseline.json`
- `tools/analyze_ruby_rom_save.py`
- `patches/pokeruby/gen10-save-extension.patch`
- `patches/pokeruby/gen10-mon-metadata-movement.patch`
- `patches/pokeruby/gen10-save-migration.patch`

## Generation X capacity policy

Target representations:

- species IDs: 16-bit;
- move IDs: 16-bit;
- item IDs: 16-bit;
- ability IDs: 16-bit;
- Pokédex numbers: 16-bit;
- type IDs: 8-bit;
- generation IDs: 8-bit;
- form IDs: 16-bit reserved, with form behavior deferred.

The legacy 0x50-byte Generation III `BoxPokemon` format remains a compatibility boundary. Direct inspection of the supplied 128 KiB saves verified 6,200 bytes of checksum-external zero-filled gap space per rotating main slot. `patches/pokeruby/gen10-save-extension.patch` now reserves 6,144 bytes of that verified space as sidecar v1, without resizing the vanilla record or changing its checksum region.

## Existing Ruby work

### External-event permanence

- `patches/pokeruby/external-events-always-on.patch`
  - Mystery Event always enabled.
  - Record-mixing event gift stock does not deplete.
  - Littleroot Town event courier supplies event tickets.
  - Existing Eon Ticket saves can repair `FLAG_SYS_HAS_EON_TICKET`.
  - Original Lilycove Harbor / Southern Island progression and encounter gates remain preserved.
- `tools/ereader_payload_extract.py`
  - RAW -> BIN -> VPK0 extraction.
  - Enigma Berry and Battle-e trainer inspection.
  - Decoration Present inspection.
- `manifests/external-events.json`
  - current external-event scope.

### Emerald-canonical item parameters

- `manifests/emerald-item-parameters.json`
- `tools/apply_emerald_item_parameters.py`
- `tools/audit_emerald_item_parameters.py`
- `patches/pokeruby/emerald-item-parameters.patch`

Ruby's item gameplay parameters are synchronized against the pinned Emerald reference where documented, while localization data remains separate.

## Current implementation order

1. audit hard-coded Generation III capacity limits;
2. normalize species/move/item/ability/dex ID representations;
3. decouple tables and loops from Generation III terminal IDs;
4. keep the implemented sidecar-v1 metadata synchronized through party / PC / daycare movement; the first movement patch is in place, while expanded-link transport remains pending;
5. integrate the modern expanded engine profile;
6. populate official content through Generation IX;
7. keep the architecture ready for official Generation X data;
8. resume form-change implementation only after the capacity/save/battle foundation is stable.

No ROM binary belongs in this repository. Source transformations, patches, manifests, reports, tools, verification logs, checksums, and other lawful non-ROM work products are tracked.
