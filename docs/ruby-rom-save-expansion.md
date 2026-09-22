# Ruby ROM / Save Baseline and Expansion Plan

## Scope

This document is based on the supplied Pokémon Ruby ROM and save images, inspected directly without modifying them, and cross-checked against `pret/pokeruby@63a8cbf0016b351a4e68f7036fa0b77e23d2f2c1`.

Japanese is the primary/origin baseline. Localized revisions are retained as compatibility evidence rather than being collapsed into the Japanese image.

No ROM or save binary is stored in this repository. Reproducible hashes and structural results are stored in `manifests/ruby-rom-save-baseline.json`, and `tools/analyze_ruby_rom_save.py` reproduces the inspection locally.

## ROM findings

The supplied Japanese ROM is `AXVJ`, revision 0, and is exactly 8 MiB. It has only 408 trailing `0xFF` bytes after the last non-`0xFF` byte, so the Japanese origin ROM has effectively no useful tail capacity for a modern all-generation expansion.

The supplied localized ROMs are 16 MiB:

| Language / region | Game code | Revisions present | Observed trailing `0xFF` tail |
| --- | --- | --- | ---: |
| Japanese | AXVJ | 0 | 408 B |
| English | AXVE | 0, 1, 2 | 1,383,868 B |
| German | AXVD | 0, 1 | 1,372,328 B |
| French | AXVF | 0, 1 | 1,371,556 B |
| Italian | AXVI | 0, 1 | 1,372,092 B |
| Spanish | AXVS | 0, 1 | 1,371,848 B |

Therefore the expanded RUBY build must **not** depend on whatever padding happens to exist in a localized 16 MiB release. The common expansion path must relink/rebuild into an expanded ROM image and preserve the original per-release ROMs only as verification inputs.

## Expanded ROM container

`patches/pokeruby/gen10-rom-capacity.patch` makes the pokeruby ROM end address configurable while preserving the original 16 MiB default. The RUBY expanded profile builds with:

```text
ROM_END=0x0A000000
```

With the cartridge ROM base at `0x08000000`, this produces a 32 MiB expanded container. This is a capacity envelope, not a claim that 32 MiB of content already exists. ROM binaries remain CI-only/local outputs and are not committed.

This avoids depending on the incidental ~1.3 MiB trailing padding observed in the 16 MiB localized retail images and gives the Japanese-origin path the same expansion ceiling.

## Save findings

Every supplied `.sav` is exactly 128 KiB and matches the Ruby flash-save layout used by the pinned source:

- 32 physical sectors;
- 4 KiB per sector;
- sectors 0-13: main save slot 1;
- sectors 14-27: main save slot 2;
- sectors 28-29: Hall of Fame reservation;
- sectors 30-31: special/e-Reader-related reservation in the original engine;
- main-sector footer begins at `0xFF4`;
- footer fields are section ID, checksum, signature `0x08012025`, and save counter;
- the two main slots rotate by save counter and section position.

The original logical chunk sizes are:

```text
id 0     0x0890   SaveBlock2
id 1-3   0x0F80   SaveBlock1 full chunks
id 4     0x0C40   SaveBlock1 final chunk
id 5-12  0x0F80   PokemonStorage full chunks
id 13    0x07D0   PokemonStorage final chunk
```

The supplied Japanese save has one complete valid main slot (slot 2, counter 1). The supplied localized saves generally retain two complete valid rotating slots. All supplied main-section checksums validate with the original Ruby checksum algorithm.

The two supplied Italian revision saves are byte-identical, which is additional evidence that save layout is not tied to that ROM revision distinction.

## Verified sidecar capacity

The original writer clears each complete 4 KiB sector, copies only the logical chunk bytes, then places the vanilla footer at `0xFF4`. The gap between the logical chunk end and `0xFF4` is outside the vanilla checksum range.

Per logical section, the observed/derived gaps are:

```text
[1892, 116, 116, 116, 948, 116, 116, 116, 116, 116, 116, 116, 116, 2084]
```

Total per main save slot: **6,200 bytes**.

Across every supplied save, every byte in the active slot's 6,200-byte gap stream is zero. This agrees with the original writer, which clears the sector before copying the ordinary save chunk.

Sectors 28-31 are also zero in the supplied saves, but they are **not** treated as free expansion space because the original engine reserves those sectors for Hall of Fame and special/e-Reader data.

## RUBY sidecar v1

`patches/pokeruby/gen10-save-extension.patch` uses the verified per-section gaps rather than resizing the original `BoxPokemon` or replacing the 128 KiB save format.

The first sidecar version reserves `0x1800` bytes (6,144 bytes) of the verified 6,200-byte capacity, leaving 56 bytes unused. It contains:

- a magic/version/payload-size header;
- an independent CRC16;
- 428 fixed extended-mon records:
  - party: 6;
  - daycare: 2;
  - PC: 14 × 30 = 420;
- 996 bytes of global future-extension storage.

Each extended-mon record is 12 bytes and currently reserves:

- 16-bit ability ID;
- 16-bit form ID reservation;
- Tera type byte;
- ability-slot byte;
- flags;
- 32-bit reserved field.

The `formId` field is storage reservation only. Form-change runtime behavior remains deferred.

Party records are intentionally placed first in the sidecar stream so Ruby's partial link-save path can persist party extension metadata in the early save section. The sidecar transport is integrated into both ordinary sector writes and the alternate byte-programming save path.

## Compatibility rules

The classic `BoxPokemon` 0x50-byte record and the original checksum regions remain unchanged.

- An original Ruby save contains no valid sidecar header. The expanded engine initializes sidecar v1 while loading the original save normally.
- Original Ruby software ignores sidecar bytes because they are outside the logical chunk sizes/checksums.
- Saving the file again in unmodified original Ruby will zero some or all sidecar bytes. This can discard expanded-only metadata, but it does not corrupt the vanilla save data.
- RUBY must never rely on sectors 28-31 as general expansion storage.
- Future sidecar versions must be explicitly versioned and migratable.

## Next implementation work

The save transport is the first foundation layer. `patches/pokeruby/gen10-mon-metadata-movement.patch` now adds the first movement layer so the 428 extended-mon records follow ordinary party compaction, PC pickup/place/shift/release operations, SendMonToPC placement, and daycare deposit/withdraw/slot-shift operations.

Expanded-link transfer is intentionally still pending: the vanilla link protocol has no field for the sidecar record, so it needs an explicit expanded-to-expanded negotiation/transport design rather than silently reusing a local slot. Until that protocol is implemented, receiving a legacy-format Pokémon must not be allowed to inherit stale expanded metadata.

After the local movement layer, the next persistence work is expanded-link transport plus runtime use of the 16-bit ability ID and other modern fields so they can stop depending on Generation III's `altAbility` representation.

ROM-side table and ID expansion should proceed in parallel, but must use the Japanese 8 MiB image as the capacity baseline: the project cannot assume the larger localized ROM padding exists.


## Round-trip verification

`tools/verify_ruby_save_sidecar.py` was run against all 12 supplied Ruby save images. For every save it:

- selected the newest complete rotating slot using the original section IDs/counters;
- injected a deterministic 6,144-byte synthetic sidecar into the verified gaps;
- extracted the sidecar back byte-for-byte;
- confirmed every vanilla logical chunk remained unchanged;
- recalculated and confirmed every vanilla section checksum remained valid;
- confirmed every vanilla footer remained unchanged;
- confirmed sectors 28-31 remained untouched.

All 12 supplied saves passed this in-memory round-trip verification.


### Linker integration

The save-extension patch explicitly places `ruby_save_extension.o` text and read-only data in the classic linker script and adds its EWRAM section to `sym_ewram.txt`. The classic pokeruby linker discards sections that are not explicitly listed, so new expansion objects must be registered in all required linker/symbol lists instead of relying on wildcard placement.


### Legacy ability migration

`patches/pokeruby/gen10-save-migration.patch` deterministically seeds the 16-bit sidecar ability ID and ability-slot fields from the classic `altAbility` bit after a save is loaded. It covers party, daycare, and all 14×30 PC slots. Existing nonzero sidecar ability IDs are preserved, so later expanded-only abilities are not overwritten by the compatibility migration.
