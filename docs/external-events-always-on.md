# External Events — Always-On Design

## Definition

"Always-on" means that content originally gated by an external distribution mechanism remains obtainable/usable without that external mechanism.

It does **not** mean bypassing normal in-game rules when simply supplying the original distributed item/data is sufficient.

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

### Eon Ticket

The original Eon Ticket distribution ultimately gives the player `ITEM_EON_TICKET` and sets `FLAG_SYS_HAS_EON_TICKET`. Lilycove Harbor already checks the physical ticket first and then the event flag, and Southern Island already checks the same event state.

Therefore the always-on implementation should **not** bypass the harbor or island scripts.

Always-on flow:

1. after the game is cleared, talking to Norman runs the internal Eon Ticket delivery check;
2. if the ticket is already in the Bag or PC, nothing happens;
3. if the Southern Island legendary encounter is already complete, nothing happens;
4. otherwise Norman gives `ITEM_EON_TICKET`;
5. successful delivery sets `FLAG_SYS_HAS_EON_TICKET`;
6. Lilycove Harbor and Southern Island continue using the original game logic unchanged.

This reproduces the useful result of the external payload without requiring an e-Reader or distribution source.

### Record-mixing external gifts

Original Mystery Event data stores a quantity and `GetRecordMixingGift` decrements it.

Always-on flow:

- validate the gift exactly as before;
- return the configured item without decrementing the quantity;
- therefore an installed official event-sharing payload does not expire.

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

These replace the Enigma Berry data structure, so their complete payload data must be embedded rather than approximated as ordinary item IDs.

### Battle-e Trainer catalog

Ruby/Sapphire can receive e-Reader trainer data used by the e-Reader trainer battle flow.

Always-on implementation requirement:

- preserve original trainer structures and checksums;
- expose every verified trainer entry through an internal selector;
- never require e-Reader link mode.

### Decoration Present

Embed the original event behavior for:

- Regirock Doll
- Regice Doll
- Registeel Doll

These must use normal decoration inventory handling.

### Berry Program Update

Treat the Berry Program Update as a compatibility repair, not as a timed distribution.

Always-on implementation requirement:

- patched Ruby builds must not regress into the original Berry/RTC calendar failure mode;
- old and new saves must remain safe;
- Japanese behavior is the primary historical reference.

## Verification rules

A completed Ruby build must pass all of these:

- Mystery Event is available without entering the old unlock phrase.
- Clearing the Mystery Event saved flag cannot hide the feature.
- Norman supplies the Eon Ticket internally after game clear when it is absent.
- Receiving the Eon Ticket sets the original event flag.
- Lilycove Harbor and Southern Island retain their original checks.
- Record-mixing event gift quantity does not decrease.
- All embedded e-Reader Berry payloads validate.
- All embedded Battle-e trainer payloads validate.
- all three Regi Doll event decorations can be obtained without external hardware.
- no e-Reader or distribution ROM is required for any catalogued event.
