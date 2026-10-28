---
title: Eval results
purpose: Record of every real eval run E1 to E7 with numbers, conditions and decisions
read_when: [after an eval run, writing the README or video, tuning thresholds]
canonical_for: [eval results]
sources: [docs/engineering/testing-strategy.md]
status: active
last_verified: 2026-10-28
related: [docs/engineering/testing-strategy.md, docs/game/balance-and-tuning.md, docs/delivery/readme-outline.md]
---

# Eval results

Real results only, from real runs. No eval has run yet as of 2026-10-28. Definitions and targets: `engineering/testing-strategy.md`.

## Key facts

| Eval | Target | Latest result | Date |
|---|---|---|---|
| E1 Registration | 90%+ IoU 0.5 | Not run | |
| E2 Re-anchor identity | 95%+ | Not run | |
| E3 Taglish commands | 85%+ (40 of 50 done-when) | Not run | |
| E4 GM validity | 97% first try, 100% non-blocking | Not run | |
| E5 Sprites | 80%+ first try | Not run | |
| E6 Latency | NFR-01, 03, 05, 08 p90 met | Not run | |
| E7 Determinism | 100% | Not run | |

## How to record a run

1. Run the eval (`eval/run_eval.py` or pytest for E7).
2. Add a row to the run log below with exact numbers and conditions.
3. Update the Key facts table.
4. If a target is missed, note the decision (tune, cut, fallback) and link the tuning log in `game/balance-and-tuning.md`.

## Run log

| Date (SGT) | Eval | Set size | Conditions | Result | Target met | Commit | Notes |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## Latency samples (E6)

| Date | Night | NFR-01 p90 | NFR-03 p90 | NFR-05 p90 | NFR-07 p90 | NFR-08 p90 |
|---|---|---|---|---|---|---|
| | | | | | | |

## Smoke test timings (Phase 1)

| Date | Call | Seconds | Notes |
|---|---|---|---|
| | | | |
