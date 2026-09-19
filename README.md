# RUBY

Pokémon Ruby external-event permanence work.

## Goal

Remove external-device / limited-distribution dependency from Ruby while preserving the original event behavior as closely as practical.

### Always-on policy

- Mystery Event is always enabled for a valid save.
- External event availability must not depend on e-Reader, distribution cartridges, record mixing, or a limited distribution counter.
- Southern Island remains accessible after the normal story prerequisite, even after the one-time Latias/Latios encounter.
- Event rewards remain one-per-save unless the original event itself was repeatable. "Always-on" means permanent availability, not infinite duplicate legendary rewards.
- e-Reader content is to be embedded in an internal catalog rather than requiring external hardware.
- Original region/language behavior is preserved where data differs. Japanese is the primary reference, then Korean when applicable, then English, then the remaining official languages.

## Current engine patch

See:

- `patches/pokeruby/external-events-always-on.patch`
- `docs/external-events-always-on.md`
- `manifests/external-events.json`

The engine patch makes the Mystery Event entry permanently enabled, makes record-mixing event gifts non-depleting, and keeps Southern Island re-enterable without the Eon Ticket external flag once the normal story prerequisite is satisfied.

The content catalog tracks the remaining e-Reader/event payloads that must be embedded directly into the ROM so the entire external-event set works offline.
