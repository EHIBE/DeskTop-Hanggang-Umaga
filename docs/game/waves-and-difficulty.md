---
title: Waves and difficulty
purpose: The fixed 8-turn wave table and scaling for player count and difficulty
read_when: [implementing backend/rules/waves.py, balancing, writing wave tests]
canonical_for: [wave table, difficulty scaling, player-count scaling]
sources: [docs/DeskTop_PRD.md#wave-schedule-normal-2-players]
status: active
last_verified: 2026-10-28
related: [docs/game/enemies.md, docs/game/balance-and-tuning.md]
---

# Waves and difficulty

Waves are fixed per difficulty so the same setup always plays the same way. Each turn teaches one idea, turn 6 is the boss, turn 8 is the last stretch.

## Key facts

| Fact | Value |
|---|---|
| Turns | 8 |
| Spawn location | Named desk edge, inside the 5 cm forest border |
| Base table | Normal, 2 players |
| Module | `backend/rules/waves.py` |

## Wave schedule (Normal, 2 players)

| Turn | Spawns | Spawn edges | Design purpose |
|---|---|---|---|
| 1 | Aswang x1 | North | Teach movement and attack |
| 2 | Aswang x1, Duwende x1 (skipped if "Tabi tabi po" was said) | East, West | Teach protecting charms |
| 3 | Tikbalang x1, Aswang x1 | South, North | Teach the physical push |
| 4 | Kapre x1 | Edge farthest from the kubo | Teach smoke and reveal (smoke cut, now a slow heavy hitter) |
| 5 | Aswang x2 | Two edges | Pressure spike |
| 6 | Manananggal (upper + lower) | Lower at an edge, upper beside it | Boss, needs a plan |
| 7 | Tikbalang x1, Duwende x1, Aswang x1 | Three edges | Chaos turn |
| 8 | Aswang x2 ("Huling dilim") | Two edges | Survive this resolution and the sun rises |

## Scaling

| Setting | Change |
|---|---|
| 3 to 4 players | +1 Aswang on turns 3 and 6 |
| Madali (easy) | Enemy HP -1 (min 1), kubo HP 12 |
| Normal | As above, kubo HP 10 |
| Mahirap (hard) | +1 Aswang on turns 3, 5 and 7, enemy ATK +1, kubo HP 8 |

## Open details (Unverified, not in the PRD)

| Detail | Proposed default |
|---|---|
| "Two edges" and "Three edges" choice | Fixed per turn in code so results stay deterministic. Pick the edges farthest from each other, starting North, clockwise |
| Extra Aswang edge | Edge farthest from the kubo |
| Spawn point along an edge | Edge midpoint, offset 5 cm per extra enemy on the same edge |
| 1 player | Use the 2-player table |

Record the chosen defaults in `balance-and-tuning.md` once coded.
