---
title: Cost and budget
purpose: Unit prices, per-call and per-night cost model, hackathon budget and guardrails
read_when: [adding a paid call, implementing the cost meter, checking spend]
canonical_for: [unit prices, cost model, budget, spend guardrails]
sources: [docs/DeskTop_PRD.md#cost-model, docs/DeskTop_PRD.md#full-cost-table]
status: active
last_verified: 2026-10-28
related: [docs/architecture/meta-api-integration.md, docs/decisions/ADR-0107-money-precision.md, docs/product/goals-and-metrics.md]
---

# Cost and budget

Expected spend is about $0.49 per night and $42.60 for the whole hackathon, against $150 of credit. The cost meter warns at $90 and blocks paid calls at $120.

## Key facts

| Fact | Value |
|---|---|
| Credit | $150 Meta Model API |
| Warn | $90 |
| Hard stop | $120, then Demo Safe Mode (FR-51) |
| Per night | About $0.49 expected, about $1.40 worst case |
| Whole hackathon | $42.60 expected, $98.88 worst case |
| Prices verified | 2026-10-25 on dev.meta.ai (recheck A5) |
| Math | Decimal (ADR-0107). Built in `backend/meta_client.py` (`price_usage`, `CostMeter`). Stored as REAL rounded to 1e-8 and summed as integers |

## Unit prices

| Model | Unit | Price |
|---|---|---|
| Muse Spark 1.3 | Input / cached input / output per 1M tokens | $1.25 / $0.15 / $4.25 |
| Muse Spark web search | Per 1,000 queries | $2.50 (not used) |
| Muse Wonder 1.0 | Input / output per 1M tokens | $4.00 / $20.00 (not used) |
| SAM 3.1 | Per 1,000 images / per 1,000 video frames | $2.50 / $0.20 (min 50 frames per video request) |
| Muse Image 1.0 | Per image | $0.01 |
| Muse Voice Transcribe 1.0 | Per hour of audio | $0.18 |
| Files API | Storage | No price listed, 100 GiB team cap |
| Muse Glimmer | Local | $0 local, Modal credits if hosted |

## Token assumptions (estimates)

A 1280 px image adds about 1,300 to 1,500 tokens. System prompt about 1,200 tokens, cached after the first call. Reasoning tokens bill as output.

## Per call

| Call | Input tokens | Output tokens | Cost |
|---|---|---|---|
| Unit card (Spark, medium) | ~3,000 | ~1,500 | 3,000 x $1.25/M + 1,500 x $4.25/M = $0.0101 |
| GM turn (Spark, low) | ~4,500 (1,200 cached) | ~850 | 1,200 x $0.15/M + 3,300 x $1.25/M + 850 x $4.25/M = $0.0079 (PRD rounds to $0.0081, per-night totals keep the PRD figure) |
| Command fallback (Spark, minimal) | ~1,500 | ~300 | $0.0032 |
| Recap (Spark, low) | ~4,000 | ~800 | $0.0084 |
| SAM image | 1 image | n/a | $0.0025 |
| SAM replay video | ~400 frames | n/a | $0.08 |
| Muse Image sprite | 1 image | n/a | $0.01 |
| Voice | ~18 min | n/a | 0.3 h x $0.18 = $0.054 |

## Per night

| Item | Expected (8 objects, 2 players) | Worst case (12 objects, re-rolls, retries) |
|---|---|---|
| Spark unit cards | 8 x $0.0101 = $0.081 | 24 x $0.0101 = $0.242 |
| Spark GM | 10 x $0.0081 = $0.081 | 15 x $0.012 = $0.180 |
| Spark command fallback and claim | 17 x $0.0032 = $0.054 | 40 x $0.0032 = $0.128 |
| Spark recap | $0.008 | $0.010 |
| SAM summon and calibration | 9 x $0.0025 = $0.023 | 25 x $0.0025 = $0.063 |
| SAM End Turn and recovery | 12 x $0.0025 = $0.030 | 34 x $0.0025 = $0.085 |
| SAM replay | $0.080 | 2 runs x 600 frames = $0.240 |
| Muse Image | 8 x $0.01 = $0.080 | 36 x $0.01 = $0.360 |
| Voice | $0.054 | 0.5 h = $0.090 |
| Total | about $0.49 | about $1.40 |

With F12 cut, the command fallback line mostly disappears. Recompute from api_usage after Playtest 2.

## Whole hackathon

| Resource | Expected | Worst case |
|---|---|---|
| SAM images | 2,000 = $5.00 | 4,800 = $12.00 |
| SAM video | 50,000 frames = $10.00 | 125,000 frames = $25.00 |
| Muse Image | 300 = $3.00 | 800 = $8.00 |
| Voice | 20 h = $3.60 | 50 h = $9.00 |
| Muse Spark | 10M in + 2M out = $21.00 | 24M in + 3.5M out = $44.88 |
| Total | $42.60 | $98.88 |
| Headroom of $150 | $107.40 | $51.12 |

## Cost meter rules

Voice is metered in 60 s slices plus the remainder at each connection end, logged as kind `voice`. A hard stop ends the session, and voice stops while the night is paused (built M11).

- Log every call to `api_usage` with tokens, images, frames, audio seconds, cost, latency, ok.
- Check the running sum before each paid call. At $120 block and switch to Demo Safe Mode.
- Each attempt reserves a worst-case estimate (`UNMETERED_CALL_ESTIMATE_USD` in `config.py`) while it is in flight, so parallel calls cannot all pass the check. Timeouts and 5xx answers are charged that estimate because the provider may still bill them.
- Alert above $3 per night.
- Tests run on fixtures, never paid calls.
- Check credits at the start of each day (Build Guide daily routine).
