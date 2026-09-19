# External Events — Always-On Design

## Definition

"Always-on" means that content originally gated by an external distribution mechanism remains obtainable/usable without that external mechanism.

It does **not** mean endlessly duplicating one-time story or legendary rewards. Access remains permanent; one-time reward semantics may remain one-time.

## Ruby external-event surfaces

### Mystery Event system

Ruby/Sapphire expose a Mystery Event VM capable of:

- running an event script
- installing a RAM script
- replacing the Enigma Berry payload
- awarding a ribbon
- enabling National Dex
- adding a rare Easy Chat word
- setting a record-mixing gift
- giving a Pokémon
- installing an e-Reader/Battle Tower trainer
- enabling RTC reset

The main-menu gate is `FLAG_SYS_EXDATA_ENABLE`. The engine layer changes this from a saved unlock into an invariant: Mystery Event is always enabled.

### Eon Ticket / Southern Island

Original flow:

1. external Mystery Event payload installs a Norman/Petalburg Gym RAM script;
2. Norman gives `ITEM_EON_TICKET`;
3. `FLAG_SYS_HAS_EON_TICKET` gates the Lilycove ferry and Southern Island encounter;
4. Ruby/Sapphire normally block returning after the encounter.

Always-on flow:

- keep the normal game-clear ferry prerequisite;
- remove the external Eon Ticket flag from ferry access;
- remove the Eon Ticket flag from the Southern Island encounter script;
- keep `FLAG_ENCOUNTERED_LATIAS_OR_LATIOS` for the one-time legendary encounter;
- do not use the encounter flag to block future ferry trips.

This makes the location permanently accessible without generating duplicate legendary encounters.

### Record-mixing external gifts

Original Mystery Event data stores a quantity and `GetRecordMixingGift` decrements it.

Always-on flow:

- validate the gift exactly as before;
- return the configured item without decrementing the quantity;
- therefore official event sharing does not expire.

### e-Reader Berry catalog

The internal catalog must preserve all 12 Ruby/Sapphire e-Reader Berry payload families:

- Pumkin
- Drash
- Eggant
- Strib
- Chilan
- Nutpea
- Ginema
- Kuo
- Yago
- Touga
- Niniku
- Topo

The payload includes more than an item ID; it replaces the Enigma Berry data structure. Therefore each official payload must be embedded, not approximated as a normal Berry item.

### Battle-e Trainer catalog

Ruby/Sapphire can receive e-Reader trainer data used in Mossdeep City / Battle Tower related flows.

Always-on implementation requirement:

- preserve original trainer structures and checksums;
- expose every preserved Series 1, Series 2, and promotional trainer entry through an internal selector;
- never require e-Reader link mode.

### Decoration Present

Embed the original event behavior for:

- Regirock Doll
- Regice Doll
- Registeel Doll

These must be granted through normal decoration inventory rules so full-inventory behavior is preserved.

### Berry Program Update

Treat the Berry Program Update as a compatibility repair, not a timed event.

Always-on implementation requirement:

- patched Ruby builds must not regress into the original Berry/RTC calendar failure mode;
- the repair state must be safe for old saves and new saves;
- Japanese update behavior is the primary historical reference.

## Implementation layers

1. **Engine permanence** — implemented by the patch in this repository.
2. **Embedded official payload catalog** — e-Reader Berries, Battle-e Trainers, Decoration Present, Eon Ticket presentation/data.
3. **Region/revision binding** — Japanese first; then English and all remaining official Ruby revisions.
4. **ROM patch tables** — exact verified offsets/signatures per clean ROM revision.
5. **Save migration** — existing saves gain always-on behavior without needing a new game.

## Verification rules

A completed Ruby build must pass all of these:

- Mystery Event entry is visible on a valid save without entering the old unlock phrase.
- Disabling the Mystery Event flag cannot hide the entry.
- Southern Island can be revisited after the legendary encounter.
- The legendary encounter itself remains one-time unless a separate repeatable-encounter option is intentionally enabled.
- Record-mixing event gift quantity does not decrease.
- All embedded e-Reader Berry payloads validate.
- All embedded Battle-e trainer payloads validate.
- all three Regi Doll event decorations can be obtained without external hardware.
- no e-Reader or distribution ROM is required for any catalogued event.
