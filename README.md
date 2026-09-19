# RUBY

Pokémon Ruby external-event permanence work.

## Goal

Remove external-device / limited-distribution dependency from Ruby while preserving the original in-game event behavior.

### Always-on policy

- Mystery Event is always enabled for a valid save.
- External event availability must not depend on e-Reader, distribution cartridges, record mixing, or a limited distribution counter.
- Ticket events keep the original destination/story gates; an in-game courier supplies the ticket itself.
- One-time story/battle rewards remain one-time unless the original event was repeatable.
- e-Reader content is converted into an internal catalog rather than requiring external hardware.
- Japanese material is the primary reference; Korean follows when applicable, then English, then other official languages.

## Current work

- `patches/pokeruby/external-events-always-on.patch`
  - Mystery Event always enabled.
  - Record-mixing event gift stock does not deplete.
  - A new Littleroot Town courier gives the Eon Ticket directly.
  - The courier also repairs `FLAG_SYS_HAS_EON_TICKET` if an existing save already owns the ticket.
  - Original Lilycove Harbor / Southern Island postgame and encounter checks are preserved.
- `tools/ereader_payload_extract.py`
  - dependency-free RAW -> BIN -> VPK0 decode pipeline.
  - checksum-based Enigma Berry and Battle-e trainer extraction.
  - multi-strip Decoration Present inspection.
- `manifests/external-events.json`
  - complete current event-work scope.
- `manifests/ereader-sources.json`
  - Japanese-first archival/source provenance without vendoring card dumps.
- `docs/ereader-payload-pipeline.md`
  - verified extraction details.

The next implementation layer is the generated internal event catalog and the in-game delivery/selection paths for the 12 e-Reader Berries, all catalogued Battle-e trainers, and all three Regi dolls.
