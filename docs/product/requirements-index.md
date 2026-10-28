---
title: Requirements index
purpose: Traceability matrix for every FR and NFR with priority, feature group, owning module, test and status
read_when: [starting or finishing any feature, checking what is built, writing tests]
canonical_for: [requirement status, FR to module map, NFR targets list, F01 to F24 feature groups]
sources: [docs/DeskTop_PRD.md#9-functional-requirements, docs/DeskTop_PRD.md#10-non-functional-requirements, docs/DeskTop_PRD.md#203-feature-prioritization-rice, docs/DeskTop_Build_Guide.md]
status: active
last_verified: 2026-10-28
related: [docs/product/scope-and-cuts.md, docs/engineering/testing-strategy.md, docs/architecture/backend-modules.md]
---

# Requirements index

Every functional and non-functional requirement with where it lives and its build status. Acceptance criteria text stays canonical in PRD sections 9 and 10, this file tracks status.

## Key facts

| Fact | Value |
|---|---|
| Functional requirements | FR-01 to FR-56 |
| Non-functional | NFR-01 to NFR-31 |
| Demo-critical (★) | 31 FRs |
| Status values | Planned, Built, Tested, Cut, Could |
| Status on 2026-10-28 | M0 to M11 built, the MVP scope is complete offline. Phase 12 (F11, F08) is next. Rows below give each test |

Update the Status column when a requirement is built (code merged) and tested (test green). Use the `desktop-docs-sync` skill.

## Feature groups

| F | Feature | MoSCoW | RICE | Hours | FRs | Status |
|---|---|---|---|---|---|---|
| F01 | Calibration and play area | Must | 4.50 | 2 | FR-01 to FR-04 | Planned |
| F02 | Summon: detection, masks, cards, caps | Must | 4.20 | 5 | FR-06 to FR-10, FR-14 to FR-16 | Built (live Spark and SAM runs wait on the key) |
| F03 | Sprite pipeline | Must | 5.25 | 4 | FR-11 to FR-13 | Built (placeholder and enemy art wait on the key) |
| F04 | Tracker overlay and occlusion freeze | Must | 5.25 | 4 | FR-26, FR-27 | Tested (offline) |
| F05 | End Turn re-anchor and drift reconcile | Must | 4.50 | 3 | FR-28, FR-29 | Built (End Turn trigger in M7) |
| F06 | Rules engine, turn loop, HUD, campaign | Must | 4.25 | 6 | FR-05, FR-31 to FR-34, FR-37, FR-40 | Tested (HUD run check Manual: EHIBE) |
| F07 | Aswang, Manananggal, telegraph | Must | 8.50 | 2 | FR-35 | Tested |
| F08 | Tikbalang, Duwende, Kapre effects | Should | 2.80 | 3 | FR-36 | Planned (Kapre smoke cut) |
| F09 | GM narration and line bank | Must | 5.67 | 3 | FR-38, FR-39 | Built (live Spark check Manual: EHIBE) |
| F10 | Voice, grammar, captions, chips, PTT | Must | 4.20 | 4 | FR-17, FR-19, FR-20, FR-22, FR-24 | Built (live Taglish run and E3 Manual: EHIBE) |
| F11 | Voice claim and overlap | Should | 3.00 | 2 | FR-18, FR-23 | Planned (overlap detection built in M11, spoken claim waits) |
| F12 | Spark fallback parser | Should | 2.80 | 1 | FR-21 | Cut |
| F13 | Tap controls | Must (guardrail) | 2.53 | 1.5 | FR-25 | Built |
| F14 | Autosave and restore | Must (guardrail) | 1.90 | 1 | FR-41 | Tested |
| F15 | Replay | Should | 2.31 | 5 | FR-44 to FR-48 | Planned |
| F16 | Returning objects, recap, progression | Could | 0.60 | 3 | FR-42, FR-43, FR-56 | Could |
| F17 | Demo Safe Mode | Must | 9.00 | 2 | FR-50 | Built (Wi-Fi off run Manual: EHIBE) |
| F18 | Cost tracker and hard stop | Must (guardrail) | 0.95 | 1 | FR-51 | Tested |
| F19 | Muse Glimmer recap | Could | 0.10 | 4 | FR-53 | Could |
| F20 | Muse Image generated map | Could | 1.25 | 2 | FR-54 | Could |
| F21 | Strict ownership | Could | 0.90 | 1 | FR-55 | Could |
| F22 | Lost detection | Should | 2.10 | 1 | FR-30 | Cut |
| F23 | Settings screen | Could | 0.90 | 1 | FR-49 | Could |
| F24 | Delete campaign data | Must (guardrail) | 1.90 | 0.5 | FR-52 | Tested |

RICE score = Reach x Impact x Confidence / Effort. Must at 4.0+, Should 2.0 to 3.99, Could under 2.0. Guardrail features are Must regardless. Full R, I, C values: PRD 20.3.

## Functional requirements

| ID | ★ | Requirement (short) | F | JS | Owning module | Test | Status |
|---|---|---|---|---|---|---|---|
| FR-01 | ★ | List cameras and mics, open camera at 1280x720+ | F01 | JS-01 | backend/capture/camera.py, screens/Calibration.tsx | test_camera.py, test_night.py, test_server.py. Live 3 s preview check Manual: EHIBE | Tested |
| FR-02 | ★ | A4 calibration, auto-detect plus 4-tap, homography, px per cm | F01 | JS-01 | backend/capture/calibration.py | test_calibration.py (synthetic ruler within 0.5 cm). Real ruler check Manual: EHIBE | Tested (backend) |
| FR-03 | ★ | Play area 60 x 40 cm with 5 cm forest edge | F01 | JS-01 | calibration.py, screens/Calibration.tsx | test_calibration.py, run check pending EHIBE | Built |
| FR-04 | | Empty-desk baseline, camera-moved detection | F01 | JS-10 | calibration.py, db/store.py | test_calibration.py, test_store.py | Tested (backend) |
| FR-05 | | New or continue campaign, difficulty | F06 | JS-09, JS-11 | backend/db/store.py, game/night.py, screens/Start.tsx | test_server.py, test_night.py | Tested |
| FR-06 | ★ | Summon one object by voice or typed name, card in 8 s p90 | F02 | JS-02 | backend/vision/summon.py, game/night.py, screens/Summon.tsx | test_summon.py, test_night.py, test_server.py. 8 s p90 is E6, Manual: EHIBE | Built (typed name. Voice summon, the ENDPOINTING session, is not built) |
| FR-07 | ★ | Spark detects new object box (0 to 1000 grid, clamped) | F02 | JS-02 | vision/summon.py, gm/schemas.py | test_summon.py, test_schemas.py. E1 Manual: EHIBE | Built |
| FR-08 | ★ | One SAM image call with box prompts, IDs 1 to 16 | F02 | JS-02 | backend/vision/sam.py | test_vision.py (records and prompts). Fixture test waits on a real SAM fixture | Built |
| FR-09 | ★ | Unit card from fixed class and power lists | F02 | JS-02 | vision/summon.py, gm/schemas.py | test_schemas.py, test_summon.py | Tested |
| FR-10 | ★ | Clamp card to class template and caps | F02 | JS-02 | backend/rules/units.py | test_units.py (100% coverage) | Tested |
| FR-11 | ★ | Placeholder class sprite in the same frame | F03 | JS-02 | canvas/sprites.ts, assets/sprites/placeholders | manual. Class-initials fallback until `smoke/assets.py` runs (Manual: EHIBE) | Built |
| FR-12 | ★ | Muse Image sprite, chroma key, palette lock | F03 | JS-02 | backend/vision/sprites.py | test_sprites.py, test_sprite_service.py. Live run and E5 Manual: EHIBE | Tested (offline) |
| FR-13 | | Sprite cache by key, no repeat call | F03 | JS-09 | vision/sprites.py, db/store.py | test_sprite_service.py, test_store.py | Tested |
| FR-14 | | Tap-to-select fallback for new object | F02 | JS-02 | game/night.py, screens/Summon.tsx | test_server.py, test_summon.py | Tested (backend) |
| FR-15 | ★ | Exactly one kubo as first summon | F02 | JS-12 | rules/units.py | test_units.py | Tested |
| FR-16 | | Cap 12 objects, 2 Charms, 2 Walls | F02 | JS-02 | rules/units.py, vision/summon.py | test_units.py, test_summon.py | Tested |
| FR-17 | ★ | Voice session per phase, ENDPOINTING then DIARIZATION | F10 | JS-03 | backend/voice/session.py, game/night.py | test_voice_session.py, test_voice_flow.py. Live fixture Manual: EHIBE | Built (night DIARIZATION session only) |
| FR-18 | | Voice claim maps labels to players and units | F11 | JS-03 | backend/voice/claim.py | unit test | Planned |
| FR-19 | ★ | Live partial and final captions with speaker chip | F10 | JS-04 | hud/Captions.tsx, hud/OrderChips.tsx | test_voice_flow.py (caption messages). Display Manual: EHIBE | Built |
| FR-20 | ★ | Local Taglish and English command grammar under 20 ms | F10 | JS-03 | backend/voice/grammar.py | test_grammar.py (triggers, Taglish examples, misfires, under 20 ms median). E3 Manual: EHIBE | Tested |
| FR-21 | | Spark fallback parser | F12 | JS-03 | n/a | n/a | Cut |
| FR-22 | ★ | Order chip before resolve, "hindi" or X cancels | F10 | JS-04 | hud/OrderChips.tsx, voice/grammar.py | test_grammar.py, test_voice_flow.py (voice chip, spoken cancel) | Tested |
| FR-23 | | Detect overlapping speakers, "Isa-isa lang!" | F11 | JS-03 | voice/session.py | test_voice_session.py (overlap drops both) | Built (claim half waits for F11) |
| FR-24 | ★ | Push-to-talk (hold Space), mode switch | F10 | JS-10 | hud/VoiceControls.tsx, game/night.py, voice/session.py | test_voice_session.py, test_voice_flow.py. Space key Manual: EHIBE | Built |
| FR-25 | ★ | Tap menu for every voice action | F13 | JS-14 | hud/TapMenu.tsx | test_night_flow.py (intent validation). TapMenu.tsx | Built |
| FR-26 | ★ | Local tracker, sprites follow at 10 Hz+, render 30 FPS+ | F04 | JS-05 | backend/capture/tracker.py, game/night.py, screens/Summon.tsx | test_tracker.py benchmark: 12 KCF trackers 31.9 ms median per update on a synthetic 1200x800 frame. Real-desk check Manual: EHIBE | Tested |
| FR-27 | ★ | Freeze sprite on tracker loss, re-lock within 1 s | F04 | JS-07 | capture/tracker.py | test_tracker.py, test_tracking_flow.py | Tested |
| FR-28 | ★ | Re-anchor all objects with one SAM call at End Turn | F05 | JS-05 | vision/sam.py, game/night.py (`reanchor_all`) | test_reanchor.py, test_tracking_flow.py. E2 Manual: EHIBE | Built |
| FR-29 | ★ | Drift reconcile and identity recovery ladder | F05 | JS-07 | vision/sam.py, vision/signature.py | test_reanchor.py (every ladder step) | Tested |
| FR-30 | | Lost detection off play area | F22 | JS-05 | n/a | n/a | Cut |
| FR-31 | ★ | Turn state machine per PRD section 8 | F06 | JS-11 | backend/game/state_machine.py | test_state_machine.py (100% coverage), test_night_flow.py | Tested |
| FR-32 | ★ | Move rings, green check or red dashed X | F06 | JS-05 | canvas/rings.ts, rules/geometry.py | test_geometry.py. Rings drawn in canvas/rings.ts | Tested |
| FR-33 | ★ | Block End Turn on illegal move, show ghost | F06 | JS-05 | game/state_machine.py | test_night_flow.py (illegal move returns to PLAYER_PHASE with endturn.blocked) | Tested |
| FR-34 | ★ | Deterministic combat resolution | F06 | JS-06 | backend/rules/resolve.py | test_resolve.py, E7 50 boards x 2 identical | Tested |
| FR-35 | ★ | Spawn waves, move enemies, intent arrows | F07 | JS-06 | rules/waves.py, rules/enemies.py, canvas/arrows.ts | test_waves.py, test_enemies.py. Arrows in canvas/arrows.ts | Tested |
| FR-36 | | Tikbalang push, Duwende steal, Kapre smoke | F08 | JS-06 | rules/enemies.py, game/night.py | test_enemies.py | Planned (smoke cut) |
| FR-37 | ★ | Win and lose, sunrise or defeat | F06 | JS-11 | rules/resolve.py, screens/Sunrise.tsx | test_resolve.py, test_night_flow.py. Screens Sunrise.tsx, Defeat.tsx | Tested |
| FR-38 | ★ | GM narration, strict JSON, captions in 6 s p90 | F09 | JS-03 | backend/gm/narrator.py | test_narrator.py (schema, repair, safety, chain), test_narration_flow.py. E4 and the 6 s p90 need the key, Manual: EHIBE | Built |
| FR-39 | ★ | Local line bank fallback for every moment | F09 | JS-10 | gm/narrator.py, assets/lines.json | test_narrator.py (every moment, priority, placeholders), test_narration_flow.py (timeout, failure, Demo Safe) | Tested |
| FR-40 | ★ | Full HUD updates within 1 frame | F06 | JS-06 | hud/*, screens/Night.tsx | manual (HUD built, Manual: EHIBE run check) | Built |
| FR-41 | | Autosave each turn, restore after crash | F14 | JS-10 | game/night.py, db/store.py | test_night_flow.py (restart resumes the saved turn exactly, interrupted night scores like a straight one, corrupt board refused), test_store.py (saved_night, v1 to v2 migration) | Tested |
| FR-42 | | Recognize returning objects | F16 | JS-09 | vision/signature.py | n/a | Could |
| FR-43 | | "Kagabi..." recap next night | F16 | JS-09 | gm/narrator.py | n/a | Could |
| FR-44 | | Recording consent from every player | F15 | JS-08 | screens/*, game/night.py | unit test | Planned |
| FR-45 | | Record warped feed to H.264 MP4 | F15 | JS-08 | backend/capture/recorder.py | manual | Planned |
| FR-46 | | Pick 4 to 6 highlights from turn_log | F15 | JS-08 | backend/replay/highlights.py | unit test | Planned |
| FR-47 | | SAM video tracking on 10 FPS proxy, reel render | F15 | JS-08 | replay/proxy.py, replay/render.py | manual | Planned |
| FR-48 | | Export 1080p MP4, 60 s max, dawn title card | F15 | JS-08 | replay/render.py | manual | Planned |
| FR-49 | | Settings screen | F23 | JS-14 | screens/Settings.tsx | n/a | Could |
| FR-50 | ★ | Demo Safe Mode completes 8 turns offline | F17 | JS-10, JS-13 | backend/game/demo_safe.py | test_demo_safe.py (8 turns with no SAM or Spark calls when the SAM toggle is off). Wi-Fi off dry run Manual: EHIBE | Built |
| FR-51 | | Cost tracker, warn $90, block at $120 | F18 | JS-13 | backend/meta_client.py, db/store.py, game/night.py, components/CostMeter.tsx | test_meta_client.py, test_server.py (hard stop turns Demo Safe on) | Tested |
| FR-52 | | Delete campaign data, no files remain | F24 | JS-10 | db/store.py | test_store.py (rows, campaign folder, owned sprites, shared sprites kept, leftover files reported), test_server.py (campaign.delete) | Tested |
| FR-53 | | Muse Glimmer recap | F19 | JS-09 | n/a | n/a | Could |
| FR-54 | | Muse Image generated barrio map | F20 | JS-02 | n/a | n/a | Could |
| FR-55 | | Strict ownership by voice label | F21 | JS-03 | n/a | n/a | Could |
| FR-56 | | Barrio level, badges, scars | F16 | JS-09 | n/a | n/a | Could |

## Non-functional requirements

| ID | Category | Target | Verified by | Status |
|---|---|---|---|---|
| NFR-01 | Latency | Summon to card with placeholder 8 s p90 | E6 | Planned |
| NFR-02 | Latency | Real sprite 30 s p90, never blocks | E6. Never blocks: background task (test_server.py) | Built |
| NFR-03 | Latency | End Turn to first animation 4 s p90 | E6 | Planned |
| NFR-04 | Latency | Rules resolution 50 ms for 12 units and 8 enemies | test_resolve.py perf: 1.1 ms median for 12 units and 8 enemies | Tested |
| NFR-05 | Latency | Speech end to chip, grammar path 3 s p90 | E6 | Planned |
| NFR-06 | Latency | Speech end to chip, Spark path 6 s p90 | n/a (F12 cut) | Cut |
| NFR-07 | Latency | Partial caption 1.5 s p90 | E6 | Planned |
| NFR-08 | Latency | Narration caption 6 s p90, animations never wait | E6 | Planned |
| NFR-09 | Performance | Overlay 30 FPS+ at 1080p | manual | Planned |
| NFR-10 | Performance | Tracker 10 Hz+ with 12 objects at 640x360 | benchmark (31.9 ms median, about 31 Hz, synthetic frame) | Tested |
| NFR-11 | Performance | Backend CPU under 70% on 4 cores in PLAYER_PHASE | manual | Planned |
| NFR-12 | Reliability | Timeouts: Spark 20 s, SAM image 10 s, SAM video 120 s, Muse Image 45 s, Files 60 s | unit test (test_meta_client.py) | Tested |
| NFR-13 | Reliability | 2 retries, 0.5 s then 1 s, jitter 250 ms, Retry-After, no retry on 400 | unit test (test_meta_client.py) | Tested |
| NFR-14 | Reliability | Breaker: 3 failures opens fallback 2 min | unit test (test_meta_client.py) | Tested |
| NFR-15 | Reliability | Graceful degradation per model | dry run | Planned |
| NFR-16 | Reliability | Voice reconnect rules, silence frames | test_voice_session.py (backoff, 1008 retry, normal close reconnect, PTT silence frames) | Built |
| NFR-17 | Reliability | Crash resume within 15 s | manual | Planned |
| NFR-18 | Cost | Per night $0.50 expected, $1.40 worst | api_usage | Planned |
| NFR-19 | Cost | Warn $90, stop $120 | unit test (test_meta_client.py) | Tested |
| NFR-20 | Privacy | Consent each night, REC dot | manual | Planned |
| NFR-21 | Privacy | Local-first data boundary | security review | Planned |
| NFR-22 | Privacy | Proxy expires 86,400 s, deleted after processing, delete campaign | unit test | Planned |
| NFR-23 | Privacy | Standard mode only | config review | Planned |
| NFR-24 | Security | Key in safeStorage, backend only | security review (M3) | Built |
| NFR-25 | Security | 127.0.0.1 only, per-launch token on every request | unit test (test_server.py) | Tested |
| NFR-26 | Accessibility | Pixel font 16 px min at 1080p, captions always on | manual | Planned |
| NFR-27 | Accessibility | Shape plus color on rings and arrows | manual | Planned |
| NFR-28 | Accessibility | Tap path for every voice action | manual | Planned |
| NFR-29 | Portability | Windows 10 and 11 first | manual | Planned |
| NFR-30 | Content | Profanity filter, content policy fallback | unit test (test_schemas.py, test_summon.py) | Tested (filter). Content policy fallback in M5 |
| NFR-31 | Maintainability | Rules coverage 90%+, fixture test per model integration | coverage 99% on rules (2026-10-28). Model fixture tests wait on real fixtures | Built |
