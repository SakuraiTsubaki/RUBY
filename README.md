# RUBY

Pokémon Ruby external-event permanence work.

## Goal

Remove external-device / limited-distribution dependency from Ruby while preserving the original in-game event behavior.

### Always-on policy

- Mystery Event is always enabled for a valid save.
- External event availability must not depend on e-Reader, distribution cartridges, record mixing, or a limited distribution counter.
- Ticket events keep their original game logic: the patch supplies the ticket internally instead of bypassing the ticket checks.
- One-time story/battle rewards remain one-time unless the original event was repeatable.
- e-Reader content is embedded into an internal catalog rather than requiring external hardware.
- Original region/language behavior is preserved where data differs. Japanese is the primary reference, then Korean when applicable, then English, then the remaining official languages.

## Current engine patch

See:

- `patches/pokeruby/external-events-always-on.patch`
- `docs/external-events-always-on.md`
- `manifests/external-events.json`

The current engine layer makes Mystery Event permanently enabled, makes record-mixing event gifts non-depleting, and delivers the Eon Ticket internally through Norman after game clear while preserving the original Lilycove Harbor and Southern Island checks.

The remaining work is to embed and verify the official e-Reader/event payload catalog so every external event works offline.
