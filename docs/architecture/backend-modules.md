---
title: Backend modules
purpose: Every planned backend module with its single responsibility, public interface, dependencies and build phase
read_when: [creating or changing any file under backend/]
canonical_for: [backend module responsibilities, backend layering, backend interfaces]
sources: [docs/DeskTop_PRD.md#project-setup-and-folder-structure, docs/DeskTop_Build_Guide.md, backend/server.py]
status: active
last_verified: 2026-10-28
related: [docs/architecture/overview.md, docs/engineering/coding-standards.md, docs/product/requirements-index.md]
---

# Backend modules

The backend follows the PRD folder tree. Each module has one job, and dependencies point inward toward the pure rules engine.

## Key facts

| Fact | Value |
|---|---|
| Language | Python 3.11 |
| Framework | FastAPI on uvicorn, 127.0.0.1:8765 |
| Exists today | `server.py` (GET /health), empty `__init__.py` in capture, vision, voice, gm, rules, game, replay, db, smoke, tests |
| Layering | server (entry) to game (orchestration) to vision, voice, gm, replay, capture (I/O services) to rules (pure) and db (persistence) |
| Injection | FastAPI Depends and constructor parameters. No module-level clients |

## Layer rules

- `rules/` imports nothing from other backend packages. No I/O, clock or randomness.
- `game/` orchestrates. It calls services and rules, and writes through `db/store.py`.
- Services (`vision`, `voice`, `gm`, `replay`, `capture`) depend on Protocols, not on each other's concrete classes.
- Only `meta_client.py` talks to Meta. Only `db/store.py` talks to SQLite.
- `server.py` stays thin: authenticate, validate, delegate, respond.

## Module map

| Module | Responsibility | Public interface (planned) | Depends on | Phase |
|---|---|---|---|---|
| `server.py` | FastAPI app, `/health`, `/ws`, token check, lifecycle | `app` | game, config | 3 |
| `config.py` | Constants: px per cm, thresholds, timeouts, prices, paths | Typed constants | none | 1 |
| `meta_client.py` | OpenAI client factory, retries, breaker, timeouts, cost meter, api_usage log | `MetaClient` with typed call methods | openai, db.store | 1, 5 |
| `state.py` | Shared live state: latest warped frame, poses | `LiveState` | none | 3 |
| `capture/camera.py` | Open camera (DirectShow), frame loop thread | `Camera` | opencv | 2 |
| `capture/calibration.py` | A4 homography, warp, camera-moved check | `homography()`, `warp()`, `is_camera_moved()` | opencv, numpy | 2 |
| `capture/tracker.py` | KCF or CSRT per object, freeze on loss, EMA smoothing | `TrackerSet` | opencv | 6 |
| `capture/recorder.py` | ffmpeg H.264 recorder with consent gate | `Recorder` | subprocess | 13 |
| `vision/summon.py` | Spark detection plus unit card | `detect_new_object()` | meta_client, gm.schemas | 4 |
| `vision/sam.py` | Box prompts, re-anchor, recovery ladder | `segment()`, `reanchor()` | meta_client, meta-sam-parser | 4, 6 |
| `vision/signature.py` | HSV histogram, area, aspect, match score | `make_signature()`, `match()` | numpy, opencv | 6 |
| `vision/sprites.py` | Muse Image call, chroma key, palette lock, cache | `generate_sprite()` | meta_client, pillow, db.store | 5 |
| `voice/session.py` | Realtime WebSocket, audio pacing, close codes, mode switch | `VoiceSession` | websockets, sounddevice | 11 |
| `voice/grammar.py` | Local Taglish command parser | `parse(text, units, enemies)` | rapidfuzz | 11 |
| `voice/claim.py` | "Ako si" enrollment, unit ownership | `claim()` | rapidfuzz | 12 |
| `gm/narrator.py` | GM call, validate, repair, line bank fallback | `narrate()` | meta_client, gm.schemas | 9 |
| `gm/prompts.py` | Stable system prompts and templates | Constants | none | 4, 9 |
| `gm/schemas.py` | Pydantic models: gm_turn, unit_card, command_parse, recap | Models | pydantic | 4 |
| `rules/geometry.py` | Distances, move legality | `edge_distance_cm()`, `in_range()`, `is_move_legal()` | shapely | 7 |
| `rules/units.py` | Class templates, clamp, powers, caps | `clamp_card()`, `CLASS_TEMPLATES` | none | 4, 7 |
| `rules/enemies.py` | Stats, AI target rules, movement | `pick_target()`, `move_enemy()` | geometry | 8 |
| `rules/waves.py` | 8-turn wave table, scaling | `spawns_for(turn, difficulty, players, flags)` | none | 8 |
| `rules/resolve.py` | Turn resolution | `resolve_turn(state, intents) -> (new_state, events)` | all rules | 7 |
| `game/state_machine.py` | Turn states and transitions | `TurnStateMachine.transition(event)` | rules | 7 |
| `game/night.py` | Runs a night, autosave, physical effects wait | `Night` | state_machine, services, store | 7 to 12 |
| `game/demo_safe.py` | Demo Safe Mode switches | `DemoSafeMode` | config | 10 |
| `replay/highlights.py` | Pick 4 to 6 moments from turn_log | `pick_highlights()` | none | 14 |
| `replay/proxy.py` | ffmpeg 10 FPS proxy | `build_proxy()` | subprocess | 14 |
| `replay/render.py` | Reel render with sprites pinned to SAM tracks | `render_reel()` | opencv, pillow | 14 |
| `db/schema.sql` | Tables | SQL | none | 2 |
| `db/store.py` | SQLite read and write, transactions | `Store` | sqlite3 | 2 |
| `smoke/*.py` | Phase 1 live API checks | Scripts | meta_client | 1 |
| `tests/` | Offline pytest suite | Tests | fixtures | 7+ |

## Protocols (for dependency inversion)

| Protocol | Implementations |
|---|---|
| `Detector` | Spark detector, tap-select fallback |
| `Segmenter` | SAM segmenter, tracker-only fallback |
| `SpriteGenerator` | Muse Image generator, placeholder provider |
| `Narrator` | Spark GM, line bank |
| `Transcriber` | Diarization session, endpointing session, push-to-talk |

Fallbacks return the same shapes as live implementations (Demo Safe Mode, NFR-15).
