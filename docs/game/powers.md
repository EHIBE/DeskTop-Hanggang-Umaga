---
title: Power catalog
purpose: The twelve powers P01 to P12 with effect, target, cooldown and class access
read_when: [implementing powers in backend/rules/units.py, writing power tests, card text]
canonical_for: [P01 to P12]
sources: [docs/DeskTop_PRD.md#power-catalog]
status: active
last_verified: 2026-10-28
related: [docs/game/units-and-classes.md, docs/game/enemies.md, docs/game/combat-math.md]
---

# Power catalog

Each unit has one power chosen from its class's allowed list. Powers resolve in the player phase in the order they were confirmed, before heals and attacks.

## Key facts

| Fact | Value |
|---|---|
| Powers | 12 (P01 to P12) plus `none` for the kubo |
| Resolution order in player phase | Powers, heals, attacks |
| Cooldown unit | Turns. 0 means usable every turn |

## Catalog

| ID | Name (Tagalog) | Effect | Target | Cooldown | Classes |
|---|---|---|---|---|---|
| P01 | Gamot | Heal 2 HP, cannot exceed max | Ally within 10 cm | 0 | Healer |
| P02 | Kalasag | Ally absorbs the next 2 damage this turn | Ally within 10 cm | 1 | Healer, Wall |
| P03 | Tulak | Push enemy 8 cm straight away | Enemy in melee | 1 | Fighter |
| P04 | Tigil | Enemy skips its next attack | Enemy in range | 2 | Reach, Ranged |
| P05 | Hampas | 1 damage to every enemy within 6 cm | Area | 1 | Fighter |
| P06 | Bantay | Kubo absorbs the next 3 damage this turn | Kubo, any distance | 2 | Charm, Wall |
| P07 | Taboy | Passive aura, enemies cannot end a move within 8 cm | Self aura | Passive | Charm |
| P08 | Liwanag | Clears kapre smoke within 12 cm | Area | 1 | Charm, Scout |
| P09 | Tusok | Hits target and one more enemy within 5 cm behind it | Line | 1 | Reach |
| P10 | Sigaw | Allies within 10 cm get +1 ATK this turn | Area | 2 | Ranged |
| P11 | Habol | +2 damage against a duwende | Enemy in melee | 0 | Fighter, Scout |
| P12 | Asin | 3 damage to a manananggal lower half | Enemy in range | 2 | Charm, Ranged |

Asin (salt) follows the common folklore that salt on the lower half stops a manananggal.

## Notes

- P08 Liwanag has no effect while Kapre smoke is cut (Build Guide). Keep the power valid so cards stay legal. Unverified: whether to swap P08 out of Charm and Scout lists while smoke is cut. Default: keep it, card text still reads correctly.
- Charms have ATK 0 and no move, so their value is entirely in the power.
- P10 bonus counts in `ATK + bonuses` of the damage formula. ATK cap 3 applies to the base stat, not to this-turn bonuses. Unverified, PRD does not say. Default: cap applies to base stat only.
- Badges (Could, F16) may reduce a power's cooldown by 1.

## Tests

One test per power for effect, target validity, range with +1 cm tolerance, and cooldown tracking across turns.
