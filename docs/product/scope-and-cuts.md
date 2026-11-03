---
title: Scope and cuts
purpose: What is in v1, what is out, what was cut and the order of future cuts
read_when: [deciding whether to build something, a day slips, scoping a feature]
canonical_for: [current scope, non-goals, no-gos, current cut list, cut order]
sources: [docs/DeskTop_Build_Guide.md#the-honest-schedule, docs/DeskTop_Build_Guide.md#cut-order-if-a-day-slips, docs/DeskTop_PRD.md#4-goals-non-goals-and-success-metrics, docs/DeskTop_PRD.md#15-rabbit-holes-and-no-gos, docs/DeskTop_PRD.md#17-milestones-and-timeline]
status: active
last_verified: 2026-11-04
related: [docs/product/requirements-index.md, docs/delivery/schedule.md, docs/decisions/ADR-0109-schedule-source.md, docs/decisions/ADR-0113-post-freeze-cut-features.md]
---

# Scope and cuts

The Build Guide (Oct 27) cut several PRD features up front and owns the cut order. This file reconciles the PRD and Build Guide into one current scope (ADR-0109).

## Key facts

| Fact | Value |
|---|---|
| Cut and since built | F22 Lost detection, F12 Spark fallback parser, Kapre smoke, F16 progression, F19, F20, F21 and F23 storage. Built 2026-11-04 as backend modules after EHIBE reversed every cut (ADR-0113). Wiring in progress |
| Still cut | Tagalog TTS engine (`tts_enabled` stays off) |
| Never cut | Calibration, summon, sprites, tracking, re-anchor, rules, Aswang, Manananggal, Tikbalang push, GM, voice orders, tap, autosave, Demo Safe Mode, cost tracker, video |
| Appetite | 10 calendar days, fixed. Scope moves, the date does not |

## Current scope (v1)

| Status | Feature groups |
|---|---|
| Must | F01 calibration, F02 summon, F03 sprites, F04 tracker, F05 re-anchor, F06 rules and HUD, F07 core enemies, F09 GM, F10 voice orders, F13 tap, F14 autosave, F17 Demo Safe Mode, F18 cost tracker, F24 delete data |
| Should (kept) | F11 voice claim and overlap, F08 Tikbalang push, Duwende steal and Kapre smoke, F15 replay, F12 Spark fallback parser, F22 Lost detection |
| Could (built after the freeze, ADR-0113) | F16 progression, returning objects and recap. F19 Glimmer recap (off unless Ollama is set). F20 generated map (off by default). F21 strict ownership (off by default). F23 settings storage (screen in progress) |

## Fallbacks for the post-freeze features

Each one defaults to the pre-freeze behavior. Canonical: `docs/decisions/ADR-0113-post-freeze-cut-features.md`.

| Feature | Default or fallback |
|---|---|
| F22 Lost detection | On in the rules. If wiring slips, objects keep their last position |
| F12 Spark fallback parser | Skipped offline and in Demo Safe. Local grammar plus tap controls |
| Kapre smoke | On. P08 Liwanag clears it |
| F16 progression and recap | Recap falls back to the line bank. No Spark tie-break for returning objects |
| F19 Glimmer | Off until `DESKTOP_GLIMMER_URL` is set |
| F20 generated map | Off until the `generated_map` setting is on. Night scene stays |
| F21 strict ownership | Off until the `strict_ownership` setting is on |
| F23 settings | Storage only, defaults match earlier behavior |

## Cut order if a day slips

Canonical (Build Guide). Cut the first item that saves enough hours, the same day.

| Order | Cut | Saves |
|---|---|---|
| 1 | Duwende steal (becomes a fast weak hitter) | 1 h |
| 2 | Voice claim and overlap (labels show as A, B) | 2 h |
| 3 | Full replay reel (keep a 10 s SAM-tracked clip) | 3 h |
| 4 | Diarization (ENDPOINTING plus tap-to-claim) | 1 h |
| 5 | Evals beyond E1 and E7 | 1 h |

## Finalization cut order

The order below came before ADR-0113. ADR-0113 added the post-freeze features on top of it and spent time that the plan gave to playtests and the video.

From 2026-11-03 this order sits on top of the Build Guide order above. Canonical plan: `docs/FINALIZATION_PLAN.md`.

1. Speaker chip
2. Folklore glossary
3. CI workflow
4. Zip packaging falls back to the from-source guide in `docs/how-to-run.md`

## Non-goals (v1)

- No real-time action. Everything resolves at End Turn
- No online multiplayer. One table, one laptop
- No mobile app
- No cloud hosting or server. Backend on localhost
- No competitive PvP. Always co-op against the night
- No user accounts or login
- No monetization
- No Tagalog TTS as a requirement. Captions carry narration
- No regional languages beyond Muse Voice Transcribe's list (Cebuano and Hiligaynon are not among its 25 languages)

## Won't (v1)

Online multiplayer, accounts, mobile app, cloud sync, PvP, store, level editor.

## No-gos

- Online multiplayer, accounts, cloud sync, leaderboards
- Mobile app
- PvP mode
- Random dice combat
- Players drawing their own enemies
- Any feature that sends full raw video to the cloud
- Any model call in Contributor mode

## Rabbit holes avoided

| Rabbit hole | Decision |
|---|---|
| Real-time SAM tracking | OpenCV between turns, SAM at End Turn (ADR-0002) |
| Transparent sprite generation | Key color plus chroma key (ADR-0005) |
| Perfect speaker identity | Soft ownership, enrollment, tap override (ADR-0007) |
| Open-ended GM improvisation | Fixed waves and powers, rules engine owns numbers (ADR-0003) |
| Glimmer as memory | SQLite (ADR-0004). Glimmer only writes the optional recap |
| Runtime enemy art | Pre-generated assets |
| Hand pose detection | Tracker failure plus frame motion |
| Perspective-perfect 3D desk | One homography from an A4 sheet |
| Tagalog TTS | Captions only, TTS off |

## Post-hackathon roadmap (out of scope)

Regional folklore pack, classroom mode with teacher view, phone camera with QR pairing, wave level editor, fully offline Glimmer narration, Cebuano and other languages if the voice model adds them.
