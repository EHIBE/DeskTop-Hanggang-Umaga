---
title: Goals and metrics
purpose: Hackathon goals, product goals, success metrics and guardrail metrics with targets
read_when: [deciding priorities, defining acceptance, running evals]
canonical_for: [PG-1 to PG-5, success metrics, guardrail metrics]
sources: [docs/DeskTop_PRD.md#4-goals-non-goals-and-success-metrics]
status: active
last_verified: 2026-10-28
related: [docs/market/judging-strategy.md, docs/engineering/testing-strategy.md, docs/product/scope-and-cuts.md]
---

# Goals and metrics

DeskTop has goals per judging criterion, five product goals, measurable success metrics and hard guardrails. Every target is an estimate until measured on the dates shown.

## Key facts

| Fact | Value |
|---|---|
| Largest judging weight | Impact 30% (unverified, A1) |
| Hard spend stop | $120 of $150 credit |
| Crash rule | 0 crashes in the last 3 runs before recording |
| Narration timeout | 20 s, then local line |

## Hackathon goals by criterion

Weights unverified until Official Rules (A1). Strategy: `docs/market/judging-strategy.md`.

| Criterion | Weight | Goal | How DeskTop earns it |
|---|---|---|---|
| Impact | 30% | Judges see a real group who would use it | Filipino setting, Taglish, zero extra hardware, real playtest footage, a clear user |
| Use of Meta AI Tooling | 25% | 4 models used beyond basic integration | Spark detection feeding SAM box prompts, SAM video reel, Muse Image reference edits with palette lock, Voice diarization with Tagalog bias and keywords |
| Demo | 25% | A complete night works live and on video | Turn-based loop, Demo Safe Mode, 2.5 min video with a hook in 8 s |
| Technical Depth and Execution | 20% | Sound engineering | Hybrid tracking with drift reconcile, tested rules engine, strict JSON contracts, eval numbers, cost tracker |

## Product goals

| ID | Goal |
|---|---|
| PG-1 | Any group goes from an empty desk to turn 1 in under 5 minutes |
| PG-2 | Players never wait on the AI to take their turn |
| PG-3 | Every outcome is explainable from the rules, never random or made up |
| PG-4 | The game sounds and feels Filipino without needing Tagalog |
| PG-5 | Each night produces a replay players want to share |

## Success metrics

| Metric | Target | How measured | When (PRD date) |
|---|---|---|---|
| Full night with no crash | 3 of 3 consecutive runs | Dry-run log | Before recording |
| Object registration (IoU 0.5+ vs hand label) | 90%+ | E1 | Eval runs |
| Re-anchor identity | 95%+ over 100 End Turns | E2 | Eval runs |
| End Turn to first animation | 4 s or less p90 | turn_log timestamps | Before recording |
| Voice to command chip | 3 s or less p90 after speech ends | turn_log | Voice phase |
| Taglish intent accuracy | 85%+ on 50 utterances | E3 | Voice phase |
| Sprite accepted first try | 80%+ | Builder rating, 20 objects | Sprite phase |
| Setup time | 5 min or less | Stopwatch | Playtests |
| Night length | 12 to 18 min | turn_log | Playtests |
| Replay share intent | 2 of 2 groups would post | Post-playtest question | Playtest 2 |
| Fun rating | Average 4 of 5+ (qualitative) | Post-playtest question | Playtests |

Dates follow `docs/delivery/schedule.md` (Build Guide), which supersedes PRD dates (ADR-0109).

## Guardrail metrics

| Guardrail | Limit | Action when hit |
|---|---|---|
| Credit spend | Warn $90, hard stop $120 | Switch to Demo Safe Mode, log it |
| Cost per night | Expected under $1, alert above $3 | Inspect api_usage |
| Crash rate | 0 in last 3 runs before recording | Fix before recording, no new features |
| GM blocking play | Never. 20 s timeout then local line | Enforced in code |
| Footage retention | 24 hours max, deleted after processing | `expires_after` plus explicit DELETE |

## Non-goals (v1)

Summary. Canonical: `docs/product/scope-and-cuts.md`.
