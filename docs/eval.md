---
title: Eval results
purpose: Record of every real eval run E1 to E7 with numbers, conditions and decisions
read_when: [after an eval run, writing the README or video, tuning thresholds]
canonical_for: [eval results]
sources: [docs/engineering/testing-strategy.md]
status: active
last_verified: 2026-11-04
related: [docs/engineering/testing-strategy.md, docs/game/balance-and-tuning.md, docs/delivery/readme-outline.md]
---

# Eval results

Real results only, from real runs. As of 2026-11-04 09:00 SGT only E7 has run. The others need the API key, recorded nights or labelled data. Definitions and targets: `engineering/testing-strategy.md`.

## Key facts

| Eval | Target | Latest result | Date |
|---|---|---|---|
| E1 Registration | 90%+ IoU 0.5 | Not run | |
| E2 Re-anchor identity | 95%+ | Not run | |
| E3 Taglish commands | 85%+ (43 of 50 done-when) | Not run | |
| E4 GM validity | 97% first try, 100% non-blocking | Not run | |
| E5 Sprites | 80%+ first try | Not run | |
| E6 Latency | NFR-01, 03, 05, 08 p90 met | Not run | |
| E7 Determinism | 100% | 50 of 50 identical (100%) | 2026-11-04 08:59 SGT |

## How to record a run

1. Run the eval from the repo root: `backend\.venv\Scripts\python eval\run_eval.py <e1|e2|e3|e4|e6|e7|all>` (see `--help`). Each run writes `eval/results/<eval>-<UTC time>.json`. A missing input or key gives "not run" and no score. e1 and e2 make paid calls, print an estimate and need `--yes`. e3 only scores rows with a `recording` field, so typed phrases never count. e4 and e6 read `desktop.sqlite` with `--db`.
2. Add a row to the run log below with exact numbers and conditions.
3. Update the Key facts table.
4. If a target is missed, note the decision (tune, cut, fallback) and link the tuning log in `game/balance-and-tuning.md`.

## Run log

| Date (SGT) | Eval | Set size | Conditions | Result | Target met | Commit | Notes |
|---|---|---|---|---|---|---|---|
| 2026-10-29 11:41 | E7 | 50 seeded boards resolved twice | Offline, seeded generator from backend/tests, includes push, steal and carry cases | 50 of 50 identical (100%) | Yes | ea8de41 | eval/results/e7-20261029T034135Z.json |
| 2026-11-03 13:31 | E7 | 50 seeded boards resolved twice | Same generator, run with the P08 power list change uncommitted | 50 of 50 identical (100%) | Yes | feb69a1 plus changes | eval/results/e7-20261103T053107Z.json |
| 2026-11-03 16:37 | E7 | 50 seeded boards resolved twice | Same generator, clean tree | 50 of 50 identical (100%) | Yes | 7ba0d44 | eval/results/e7-20261103T083746Z.json |
| 2026-11-03 23:59 | E7 | 50 seeded boards resolved twice | Same generator, run with the post-freeze rules changes uncommitted | 50 of 50 identical (100%) | Yes | c5989b2 plus changes | eval/results/e7-20261103T155945Z.json |
| 2026-11-04 08:59 | E7 | 50 seeded boards resolved twice | Same generator, clean tree with every post-freeze rule committed | 50 of 50 identical (100%) | Yes | 4b90671 | eval/results/e7-20261104T005956Z.json. Command `backend\.venv\Scripts\python eval\run_eval.py e7` |

## Latency samples (E6)

Sources: NFR-01 from `summon` turn_log rows, NFR-03 from End Turn transition rows, NFR-08 from `narration` rows (request to caption publish). NFR-05 and NFR-07 have no logged timing yet and report as unmeasured until a live voice fixture confirms the speech end events.

| Date | Night | NFR-01 p90 | NFR-03 p90 | NFR-05 p90 | NFR-07 p90 | NFR-08 p90 |
|---|---|---|---|---|---|---|
| | | | | | | |

## Smoke test timings (Phase 1)

| Date | Call | Seconds | Notes |
|---|---|---|---|
| | | | |
