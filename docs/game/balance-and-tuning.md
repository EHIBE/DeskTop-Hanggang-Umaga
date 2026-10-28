---
title: Balance and tuning
purpose: Every tunable threshold and constant, its starting value and when to tune it
read_when: [tuning after evals or playtests, writing backend/config.py]
canonical_for: [tunable constants list, tuning log]
sources: [docs/DeskTop_PRD.md#re-anchor-and-drift-logic-per-object-at-end-turn, docs/DeskTop_PRD.md#unit-system, docs/DeskTop_PRD.md#10-non-functional-requirements, docs/DeskTop_Build_Guide.md]
status: active
last_verified: 2026-10-28
related: [docs/engineering/environment-and-config.md, docs/architecture/tracking-and-reanchor.md, docs/playtests.md]
---

# Balance and tuning

All thresholds are starting values. Game constants live once in `backend/rules` modules, because the rules layer imports nothing else from the backend. Vision, tracking and reliability constants live in `backend/config.py`. Never inline a number, and log every change in the tuning log below.

## Key facts

| Fact | Value |
|---|---|
| Home of constants | Game: `backend/rules/*.py`. Vision, tracking, reliability, prices: `backend/config.py` (built 2026-10-28) |
| Tune with | E1, E2 eval runs and playtests |
| Rule | Change one constant at a time and record why |

## Game constants

| Constant | Start value | Source |
|---|---|---|
| Move Short / Medium / Long | 8 / 12 / 16 cm | PRD 8 |
| Range Melee / Reach / Far | 5 / 9 / 15 cm | PRD 8 |
| Distance tolerance | +1 cm | PRD 8 |
| Enemy footprint radius | 2 cm | PRD 8 |
| Isolation radius (Aswang AI) | 10 cm | PRD 8 |
| Push distance | 8 cm | PRD 8 |
| Push compliance radius | 2 cm | FR-36 |
| Physical effect timeout | 20 s | PRD 8 |
| Turns per night | 8 | PRD 8 |
| Max objects | 12 | FR-16 |
| Kubo moved warning | 2 cm | Edge case 19 |

Rules constants as built (2026-10-28) live in `backend/rules`: `PUSH_CM` 8, `HAMPAS_RADIUS_CM` 6, `TUSOK_BEHIND_CM` 5, `KALASAG_SHIELD` 2, `BANTAY_SHIELD` 3, `HEAL_AMOUNT` 2, `ALLY_POWER_RADIUS_CM` 10, `REFORM_TURNS` 2, `REFORM_OFFSET_CM` 5, `SPAWN_OFFSET_CM` 5, `ENEMY_RADIUS_CM` 2, `DISTANCE_TOLERANCE_CM` 1, `ISOLATION_RADIUS_CM` 10, `AURA_RADIUS_CM` 8, `KUBO_MOVED_WARN_CM` 2, `TURNS_PER_NIGHT` 8.

## Vision and tracking constants

| Constant | Start value | Source |
|---|---|---|
| Warped scale | 20 px per cm | Build Guide 2.2, ADR-0105 |
| Tracking resolution | 640 px wide | Build Guide 6.1 |
| Position smoothing EMA alpha | 0.4 | Build Guide 6.1 |
| SAM accept confidence | 0.5 | PRD 12 |
| SAM vs tracker IoU accept | 0.3 | PRD 12 |
| Histogram match (Bhattacharyya) | 0.35 or less | PRD 12 |
| Recovery search radius | 15 cm | PRD 12 |
| Box padding at re-anchor | 20% | PRD 12 |
| Crop padding for sprites | 15% | PRD 12 |
| Between-turn SAM after tracker loss | 3 s with no hand motion (PRD), 5 s (Build Guide and edge case 1). Default 5 s | Conflict, see note |
| Max between-turn SAM calls | 3 per turn | PRD 12 |
| Hands-off wait at End Turn | up to 3 s | Edge case 2 |
| Summon snapshot delay | 1 s after hand leaves | F3 |
| Stack overlap | 60% | Edge case 13 |
| Brightness change alert | 30% from calibration | Edge case 9 |
| Camera moved | Grid shift over 2 cm | FR-04 |
| Chroma key HSV distance | 40 (PRD) | PRD 12. Build Guide sample uses RGB sum tolerance 60 |
| Sprite alpha coverage | 15% to 90% | FR-12 |
| Signature match | 0.8, ties within 0.05 | PRD 12 |
| Voice claim fuzzy match | Levenshtein ratio 0.75 | PRD 12 |
| Grammar fuzzy cutoff | 75 (rapidfuzz partial_ratio) | Build Guide 11.4 |

Note on tracker loss: PRD section 12 says 3 s, edge case 1 and Build Guide 6.1 say 5 s. Default to 5 s and confirm in Phase 6.

## Reliability constants

| Constant | Value |
|---|---|
| Timeouts | Spark 20 s, SAM image 10 s, SAM video 120 s, Muse Image 45 s, Files upload 60 s |
| Retries | 2, backoff 0.5 s then 1 s, jitter up to 250 ms |
| Breaker | 3 failures, 2 minutes |
| End Turn snapshot timeout | 10 s |
| Voice claim timeout | 60 s |
| Narration timeout | 20 s |
| Cost warn and stop | $90 and $120 |

## Tuning log

| Date | Constant | Old | New | Evidence |
|---|---|---|---|---|
| | | | | |
