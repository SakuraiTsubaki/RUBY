# External Events — Always-On Design

## Definition

"Always-on" means that content originally gated by an external distribution mechanism remains obtainable/usable without that external mechanism.

It does **not** mean bypassing normal in-game story rules when simply supplying the original distributed item/data is sufficient.

## Ruby external-event surfaces

### Mystery Event system

Ruby/Sapphire expose a Mystery Event VM capable of running event/RAM scripts, replacing the Enigma Berry payload, awarding ribbons, enabling National Dex, adding rare Easy Chat words, setting record-mixing gifts, giving Pokémon, installing e-Reader trainers, and enabling RTC reset.

The main-menu gate is `FLAG_SYS_EXDATA_ENABLE`. The engine layer makes Mystery Event permanently available.

### Eon Ticket — Littleroot courier

The ticket distribution is separated from the story.

A new NPC is placed in Littleroot Town near Professor Birch's Lab. The courier is present from the beginning of normal town exploration and simply hands over `ITEM_EON_TICKET`.

Flow:

1. talk to the Littleroot courier;
2. if the Eon Ticket is absent from both Bag and PC, receive one;
3. successful delivery sets `FLAG_SYS_HAS_EON_TICKET`;
4. if a migrated/older save already has the ticket, talking to the courier repairs the flag instead of creating a duplicate;
5. Lilycove Harbor and Southern Island remain unchanged.

This intentionally allows the player to possess the ticket early. It does **not** allow early travel to Southern Island because the original Lilycove script still checks `FLAG_SYS_GAME_CLEAR`. The legendary encounter's original one-time check also remains intact.

This design minimizes story changes: no Norman/postgame dialogue is replaced, and the external distribution dependency is reduced to a simple in-world courier.

### Record-mixing external gifts

Installed Mystery Event record-mixing gifts validate normally but their distribution quantity no longer decreases.

### e-Reader Berry catalog

The internal catalog preserves all 12 Ruby/Sapphire e-Reader Berry payload families: Pumkin, Drash, Eggant, Strib, Chilan, Nutpea, Ginema, Kuo, Yago, Touga, Niniku, and Topo.

These are complete `struct EnigmaBerry` payloads, not ordinary item IDs.

### Battle-e Trainer catalog

Preserve the original trainer structures/checksums and expose every verified trainer through an internal selector without requiring e-Reader link mode.

### Decoration Present

Preserve the verified O001 rewards:

- Regirock Doll
- Regice Doll
- Registeel Doll

### Berry Program Update

Treat the Berry Program Update as a compatibility repair rather than a timed distribution.

## Verification rules

- Mystery Event remains available without the old unlock phrase.
- The Littleroot courier gives exactly one Eon Ticket when none is present.
- A save that already owns the Eon Ticket does not receive a duplicate.
- Talking to the courier repairs `FLAG_SYS_HAS_EON_TICKET` for migrated saves.
- Receiving the ticket before game clear does not permit Southern Island travel.
- Lilycove Harbor keeps the original `FLAG_SYS_GAME_CLEAR`, encounter, item, and event-flag behavior.
- Record-mixing event gift quantity does not decrease.
- Embedded e-Reader Berry and Battle-e trainer payloads validate.
- all three Regi Doll decorations are obtainable without external hardware.
