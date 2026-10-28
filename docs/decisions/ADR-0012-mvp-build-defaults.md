---
title: ADR-0012 MVP build defaults
purpose: Record the defaults EHIBE approved at the MVP build clarification gate for rules, content, assets and runtime gaps the docs left open
read_when: [implementing damage, enemy movement, targeting, waves, voice claim, content filters, assets, backend startup, stage scaling]
canonical_for: [ADR-0012, damage with shields rule, duwende pre-steal hit, wall blocking rule, target tie-break, fail-closed token startup]
sources: [docs/MVP_BUILD_PROMPT.md#2-clarify-gate, docs/game/combat-math.md, docs/game/enemies.md, docs/game/waves-and-difficulty.md]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, docs/game/combat-math.md, docs/game/waves-and-difficulty.md, docs/game/powers.md]
---

# ADR-0012: MVP build defaults

Status: Accepted. Decided 2026-10-28 by EHIBE ("use defaults" at the MVP build clarification gate).

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-28 |
| Owner | EHIBE |

## Context

The PRD and derived docs leave several rules and runtime details open or contradictory. The MVP build prompt requires flagging every ambiguity before code. EHIBE approved the recommended default on each.

## Decision

| Topic | Decision |
|---|---|
| Damage with shields | Raw damage is `max(1, ATK + bonuses)`. Shield pools (P02, P06) absorb first, the rest reduces HP. A shield can block a hit fully. Event `dmg` is the HP actually lost |
| Duwende before Phase 12 | A duwende hit deals 1 damage (the cut-list "fast weak hitter"). Phase 12 replaces it with a steal and 0 damage |
| Walls | Enemies move in a straight line toward their target, no pathfinding. A non-flying enemy stops at first contact with a Wall unit footprint |
| Ties | Target and spawn ties break by nearest edge distance, then lowest SAM object ID |
| Unverified game defaults | Accepted as written: edges chosen North then clockwise and farthest apart, extra Aswang at the edge farthest from the kubo, spawn at the edge midpoint offset 5 cm per extra enemy, 1 player uses the 2-player table, P10 bonus ignores the ATK cap, P08 stays valid, tied Bayani players all shown, tracker-loss SAM delay 5 s |
| Voice claim before F11 | VOICE_CLAIM ships in the MVP with typed player names, tap-to-assign units, Skip and the 60 s timeout. Spoken claim arrives with F11 |
| Pixel font | Press Start 2P (SIL OFL 1.1) bundled in `assets/fonts/` with its license |
| Content filter lists | LDNOOBW English and Filipino lists (CC BY 4.0) and a PSGC province and city list in `backend/gm/data/`, with attribution |
| Placeholder, enemy and tile art | Generated with Muse Image in Phase 5.1 once the key is present |
| Audio | Deferred until after the MVP |
| Aswang spawn line | East, south and west variants added, marked Proposed until playtester review |
| Backend start | Refuses to start without `DESKTOP_TOKEN` (fail closed). Data root defaults to `%APPDATA%\DeskTop` when `DESKTOP_DATA_DIR` is unset |
| Stage | One fixed 1920x1080 stage scaled to fit the window with letterboxing. Sprites drawn nearest-neighbor at integer scales |
| Tailwind packages | Moved to devDependencies with versions unchanged |
| ffmpeg | Manual: EHIBE installs it before Phase 13 |

## Consequences

- Rules code and tests follow this table. Game docs point here for these rules
- Proposed copy lines still need 2 Filipino playtesters
- Asset steps wait for the key (Manual: EHIBE)

## Alternatives considered

- Literal formula `max(1, ATK + bonuses - shield)` (rejected: conflicts with "absorbs the next 2 damage")
- Pathfinding around walls (rejected: KISS, not in the PRD)
- A `"dev"` token default (rejected: fails open)

## Sources

- `docs/MVP_BUILD_PROMPT.md#2-clarify-gate`
- `docs/game/combat-math.md`
- `docs/game/waves-and-difficulty.md`
