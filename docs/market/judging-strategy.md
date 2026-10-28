---
title: Judging strategy
purpose: Rubric, scorecards, score levers and how each demo element earns points
read_when: [prioritizing work for score, planning the video, final review before submission]
canonical_for: [rubric scorecard, indie lens score, feasibility score, appeal score, score levers]
sources: [docs/DeskTop_PRD.md#20-scoring, docs/DeskTop_PRD.md#4-goals-non-goals-and-success-metrics]
status: active
last_verified: 2026-10-28
related: [docs/delivery/video-script.md, docs/market/positioning-and-messaging.md, docs/product/goals-and-metrics.md]
---

# Judging strategy

The rubric (unverified, A1) weights Impact highest, so real people playing beats extra features. The PRD scores the current plan at 81.75 of 100 and the full Must plus Should target at 88.25.

## Key facts

| Criterion | Weight | As specified | Target |
|---|---|---|---|
| Impact | 30% | 7 | 8 |
| Use of Meta AI Tooling | 25% | 9 | 9.5 |
| Demo | 25% | 8.5 | 9 |
| Technical Depth and Execution | 20% | 8.5 | 9 |
| Weighted total | 100% | 81.75 | 88.25 |

Weighted total = sum of score x weight / 10. Original DeskStage concept scored 61 (4, 7, 7, 7).

Math check: 7 x 3 + 9 x 2.5 + 8.5 x 2.5 + 8.5 x 2 = 21 + 22.5 + 21.25 + 17 = 81.75. Target: 8 x 3 + 9.5 x 2.5 + 9 x 2.5 + 9 x 2 = 24 + 23.75 + 22.5 + 18 = 88.25.

Note: the Build Guide cut F12, F22, Kapre smoke and all Coulds. None of the scored levers depend on them, so the scores stand. Rescore when the Official Rules arrive.

## How each criterion is earned

| Criterion | What judges must see | Where |
|---|---|---|
| Impact | Real Filipino friends at a real table, Taglish, no extra hardware, a named user | Video 0:08 to 0:20, 0:55 to 1:35, title card |
| Tooling | Each model doing what chat AI cannot, named on screen | Summon split screen, voice claim chips, replay reel |
| Demo | A complete night that works, with a replay | Night section, sunrise, backup recording, Demo Safe Mode |
| Technical depth | Hybrid tracking, deterministic rules with tests, strict schemas, eval numbers, cost | Under-the-hood shot, README eval table |

## Score levers (from PRD 20.8)

| Rank | Lever | Change | Points |
|---|---|---|---|
| 1 | Film real Filipino friends playing with genuine reactions as the core of the video | Impact +1, Demo +0.5 | +4.25 |
| 2 | Ship the full replay reel with SAM video and show it | Tooling +0.5, Demo +0.5 | +2.50 |
| 3 | Pre-built Windows zip and one-command setup | Demo +0.5, Tech +0.25 | +1.75 |
| 4 | A 10 s classroom clip (facilitator running a night) | Impact +0.5 | +1.50 |
| 5 | Publish E1 to E7 on screen and in the README | Tech +0.5 | +1.00 |
| 6 | Glimmer offline recap, labeled | Tooling +0.25 | +0.63 (Could, cut) |

Levers 1 and 2 together add 6.75 points, to about 88.5.

## Indie lens

| Lens | As specified | Target | Why |
|---|---|---|---|
| Creativity | 9 | 9 | Real objects, Taglish orders and folklore together are rare |
| Technical ambition | 8.5 | 8.5 | Four models, vision plus voice plus image plus tracking, solo |
| Whether it works | 7 | 8.5 | Depends on execution. Demo Safe Mode protects it |
| Average | 8.2 | 8.7 | |

## Feasibility (PRD 20.4)

| Area | Score | Note |
|---|---|---|
| Scope | 6 | 39 Must hours for one person |
| Skills fit | 8 | Builder shipped Electron with real-time voice (Merky) and FastAPI |
| Time | 5 | 66.5 planned hours (Build Guide) against 50 to 60 estimated |
| Cost | 9.5 | Worst case $98.88 of $150 |
| Model capability | 7.5 | All uses match documented limits. Latency and diarization unmeasured |
| Demo risk | 6.5 | Physical setup and tracking can look rough |
| Overall | 7.1 | Feasible if the cut order and freeze hold |

## Player appeal (PRD 20.6)

| Factor | Score |
|---|---|
| Fun | 8 |
| Novelty | 9 |
| Replayability | 6.5 |
| Shareability | 8.5 |
| Cultural resonance | 9 for Filipino players, 7 for global judges |
| Average | 8.2 |

## Risks to the score

- R12: judges discount a game on Impact. Lead with the shared-table problem and real players.
- R02: rules may change video length or required fields. Rescore within 24 h.
- Market evidence is thin on group play habits (`market-and-audience.md`). Use playtest quotes, labeled small sample.
