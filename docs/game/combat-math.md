---
title: Combat math
purpose: Deterministic rules for distance, movement, hits, damage, order and status effects
read_when: [implementing backend/rules/geometry.py or resolve.py, writing rules tests]
canonical_for: [distances, damage formula, resolution order, status effects, tolerance]
sources: [docs/DeskTop_PRD.md#combat-math-deterministic, docs/DeskTop_PRD.md#unit-system, docs/DeskTop_Build_Guide.md#71-rules-engine-layout]
status: active
last_verified: 2026-10-28
related: [docs/game/units-and-classes.md, docs/game/powers.md, docs/game/enemies.md, docs/decisions/ADR-0003-deterministic-rules-engine.md]
---

# Combat math

Every number is computed by pure functions in `backend/rules` with no I/O, clock or randomness. Same state and intents always give the same event list (E7).

## Key facts

| Rule | Value |
|---|---|
| Damage | `max(1, ATK + bonuses - shield)`. Shield absorbs first, then HP |
| Hit | Always hits if target is in range at the End Turn snapshot. No dice |
| Tolerance | +1 cm on every distance check |
| Actions per unit per turn | 1 move (by hand) and 1 action (attack, power or nothing) |
| Entry point | `resolve_turn(state, intents) -> (new_state, events)` |
| Performance | 50 ms or less for 12 units and 8 enemies (NFR-04) |

## Distances (real-world, from calibration)

| Name | Value |
|---|---|
| Move Short / Medium / Long | 8 cm / 12 cm / 16 cm |
| Range Melee / Reach / Far | 5 cm / 9 cm / 15 cm |
| Distance measure | Edge to edge between footprints. Unit footprint is the mask convex hull. Enemy footprint is a circle of radius 2 cm |
| Move measure | Centroid displacement from the turn start position |
| Noise tolerance | +1 cm on every check |

Reference implementation shape (Build Guide 7.1): shapely `Polygon(unit_hull_cm).distance(Point(enemy_xy_cm)) - 2.0`, floored at 0, and `in_range = dist <= range + 1.0`.

## Rules

| Rule | Formula or behavior |
|---|---|
| Attack with ATK 0 | Not allowed. Chip shows `cmd.no_atk` ("Walang atake si [unit]") |
| Order | Player intents resolve in confirmed order. Then enemies in spawn order |
| Enemy attack check | Re-measured after player moves. Out of range is a miss ("Nakaiwas!") |
| Down | HP 0. Sprite greys, object stays, cannot act. Healable only next night (scar) |
| Line of sight | None in v1. Walls block enemy movement paths only |
| Repel aura | Enemies cannot end a move inside a P07 aura |
| Flying | Manananggal upper half flies over walls |
| HP cap | Heals cannot exceed max HP |

## Status effects

| Status | Meaning |
|---|---|
| Shielded | Absorbs N damage this turn (P02, P06) |
| Stunned | Skips its next attack (P04) |
| Smoked | Inside kapre smoke (cut in v1, see `enemies.md`) |
| Stolen | Removed by a duwende |
| Lost | Off the desk. Cannot act or be targeted (Lost detection F22 cut, objects keep last position) |
| Uncertain | Position unknown, "?" badge until tapped or re-found |

## Events

`resolve_turn` returns an ordered event list consumed by the renderer (animations), the GM (narration) and turn_log. Event types seen in the PRD GM input: `attack`, `dodge`, `spawn`, `intent`. Implementers add `heal`, `power`, `shield`, `down`, `push`, `steal`, `return`, `escape`, `split`, `reform`, `kubo_hit`, `win`, `lose` as needed, each with `src`, `dst` and numbers. Canonical event schema: `docs/architecture/websocket-protocol.md`.

## Tests required

Edge-to-edge distance, move legality with tolerance, damage with shields, ATK 0 rejection, cooldowns, every power P01 to P12, every enemy AI rule, wave spawns per difficulty and player count, win, lose, and determinism over 50 seeded board states (E7, 100%).
