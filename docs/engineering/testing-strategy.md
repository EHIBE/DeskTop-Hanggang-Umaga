---
title: Testing strategy
purpose: Automated tests, fixtures, evals E1 to E7, playtests and CI plan
read_when: [writing tests, recording fixtures, running evals, before reporting a feature]
canonical_for: [test layout, fixture rules, E1 to E7 definitions, coverage target]
sources: [docs/DeskTop_PRD.md#18-testing-and-qa, docs/DeskTop_PRD.md#eval-plan-run-oct-29-and-again-nov-2-before-recording, docs/DeskTop_Build_Guide.md#132-evals-15-h]
status: active
last_verified: 2026-11-03
related: [docs/eval.md, docs/playtests.md, docs/product/requirements-index.md]
---

# Testing strategy

All automated tests run offline against recorded fixtures, so they cost nothing and never flake on the network. Evals measure real model quality and are recorded in `docs/eval.md` from real runs only.

## Key facts

| Fact | Value |
|---|---|
| Framework | pytest (backend). Renderer: Node built-in `node:test` with `--experimental-strip-types`, no extra dependency |
| Command | `backend\.venv\Scripts\python -m pytest backend/tests -q` and `npm --prefix app run test` |
| Coverage target | 90%+ of rules functions (NFR-31). Measure with `cd backend` then `.venv\Scripts\python -m pytest tests -q --cov=rules` |
| Python static checks | ruff check, ruff format and mypy --strict (ADR-0101). All clean on 2026-11-04 with 2,182 backend tests and 84 renderer tests passing. Coverage 96% overall, `server.py` 100%, `night.py` 93% |
| Fixtures | `fixtures/` from Phase 1 smoke tests and later recordings |
| Determinism | E7 must be 100% |
| CI | `.github/workflows/ci.yml` (Windows, Python 3.13, Node 22): ruff, ruff format, mypy strict, pytest, typecheck, lint, prettier. First run after EHIBE pushes |

## Test files

| File | Covers |
|---|---|
| `test_geometry.py` | Edge-to-edge distance, move legality with +1 cm tolerance |
| `test_units.py` | Class templates, clamp (FR-10 example), caps, kubo first |
| `test_enemies.py` | Every AI target rule, movement, walls, auras, specials |
| `test_waves.py` | Every turn per difficulty and player count, Tabi tabi po |
| `test_resolve.py` | Damage with shields, each power P01 to P12, order, win, lose, determinism E7 |
| `test_state_machine.py` | Every transition, illegal move loop, pause and resume, crash restore |
| `test_grammar.py` | 100 written Taglish and English orders with expected intents |
| `test_schemas.py` | Good and bad fixtures for unit_card and the content filter |
| `test_narrator.py`, `test_narration_flow.py` | gm_turn schema, repair, safety checks, line bank, background narration, timeout, logging |
| `test_night_flow.py`, `test_tracking_flow.py`, `test_effects_flow.py` | A full night, restore, pause, camera moved, consent, physical effects |
| `test_voice_session.py`, `test_voice_flow.py`, `test_claim.py` | Realtime session with fakes, voice orders and chips, voice claim |
| `test_physical_effects.py` | Tikbalang push and throw, duwende steal, flee, return, escape, returning units |
| `test_demo_safe.py` | Demo Safe switches and a full night with no paid calls |
| `test_recorder.py`, `test_recording_flow.py` | ffmpeg recorder with a fake process, consent gate, sidecar |
| `test_highlights.py`, `test_proxy.py`, `test_sam_video.py`, `test_render.py`, `test_replay_flow.py` | Replay highlights, proxy, upload and delete, SAM video parsing, reel render, orchestration |
| `test_run_eval.py` | Eval runner E1 to E7 and cost, not-run paths |
| `test_store.py`, `test_server.py`, `test_meta_client.py` | Persistence and migration, WebSocket protocol, Meta client retries, breaker and cost meter |

Also required: model integration tests on fixtures (Spark, SAM image, SAM video, Muse Image, voice event streams, Files), sprite pipeline on 20 saved outputs, cost meter sums with $90 and $120, privacy (delete campaign leaves no files, proxy gets DELETE), and token checks (missing or wrong token rejected).

## Fixture rules

- Record once with a live smoke call, save raw JSON or JSONL under `fixtures/`.
- Strip any key, token or Authorization header before saving.
- Name by model and case: `spark_line.json`, `sam_boxes.txt`, `sprite_kubo.png`, `voice_diar.jsonl`.
- Tests inject fixture-backed fakes through the same Protocols as live services.

## Evals

| Eval | Test set | Metric | Target |
|---|---|---|---|
| E1 Registration | 20 objects x 3 conditions (plain mat, wood desk, dim light) = 60 snapshots, hand-labeled boxes | New object found with IoU 0.5+ | 90%+ |
| E2 Re-anchor identity | 100 End Turns, 6 to 12 objects, 2 look-alike pairs | Correct ID | 95%+ |
| E3 Taglish commands | 50 utterances, 2+ speakers, target laptop mic | Correct unit, action, target | 85%+ |
| E4 GM validity | 200 GM calls from scripted nights | Valid first try / after repair | 97% / 100% non-blocking |
| E5 Sprites | 20 objects | Recognizable, clean key, on-style (builder rating) | 80%+ first try |
| E6 Latency | 3 full nights | NFR-01, 03, 05, 08 p90 | All met |
| E7 Determinism | 50 seeded board states resolved twice | Identical events | 100% |

E1 objects: mug, coin, keys, pen, eraser, phone, ID card, calculator, tumbler, stapler, tape, charger, sticky notes, ruler, spoon, earbuds case, wallet, comb, bottle cap, highlighter. Assets in `eval/objects/` and `eval/voice/`. Runner `eval/run_eval.py`.

Quick versions for the eval day (Build Guide 13.2): E1 with 20 objects in 1 condition, E2 on 50 End Turns, E3 on 50 orders, E4 by counting `gm_invalid`, E7 in pytest.

## Playtests

| # | When | Who | Setup | Measure |
|---|---|---|---|---|
| 1 | After Phase 10 | 2 friends | Tap only | Setup time, turn time, confusion, fun 1 to 5, unfair rules |
| 2 | Demo night | 2 to 3 Filipino speakers | Full build, voice, recording | Same plus order recognition, Taglish review, share intent |
| 3 (optional) | After demo | 1 new person | Full build | First-time clarity, time to first turn |

Log in `docs/playtests.md`, labeled qualitative and small sample.

## Rules

- Deterministic only. No sleeps, no network, no wall clock in assertions.
- Never weaken or skip tests to pass. Never suppress errors.
- Report real output, including failures.
