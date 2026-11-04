---
title: Build log
purpose: Dated history of every milestone and phase, moved out of CLAUDE.md State so CLAUDE.md holds current state only
read_when: [asking when or how something was built, writing the README history, auditing a past claim]
canonical_for: [build history, milestone dates]
sources: [CLAUDE.md, git log, docs/FINALIZATION_PLAN.md, docs/decisions/README.md]
status: active
last_verified: 2026-11-04
related: [CLAUDE.md, docs/FINALIZATION_PLAN.md, docs/delivery/schedule.md, docs/eval.md]
---

# Build log

This file keeps the dated history of how DeskTop was built, one row per milestone or phase. Rows moved here verbatim from CLAUDE.md State on 2026-11-04, so numbers in older rows are as they stood on that date and later rows may supersede them.

## Key facts

| Fact | Value |
|---|---|
| First commit | Scaffold 3379e9c |
| MVP scope complete offline | M11, 2026-10-28 |
| Feature freeze | Nov 3, 6:00 PM SGT, moved by ADR-0113 |
| Release zip built | 2026-11-04 at commit 5e0cff7 |
| Current state | `CLAUDE.md` State |

## Milestones and phases

Commit hashes for each row: `git log --oneline`. Superseded numbers are marked in the row.

| Item | Status |
|---|---|
| Scaffold | Done. Commit 3379e9c |
| Docs | Full AI-ready doc set added 2026-10-28 (see Docs map) |
| Project agents and skills | Added in `.claude/agents/` and `.claude/skills/` |
| M0 Foundations | Done 2026-10-28. Tailwind wired, Electron hardened, `config.py`, `db/schema.sql`, `db/store.py`, `meta_client.py` (retries, breaker, Decimal cost meter) |
| Python env | `backend/.venv` on Python 3.13.15, 48 pins in `requirements.txt` (ADR-0101) |
| M1 smoke scripts | Built 2026-10-28 (`backend/smoke`). Live runs Manual: EHIBE (key, inputs) |
| M2 camera and calibration | Backend built 2026-10-28. Real ruler check Manual: EHIBE |
| M3 app shell | Built 2026-10-28. Backend spawn on a free port with a fresh token, safeStorage key, token-gated /ws (subprotocol auth), KeySetup, Start, Calibration screens. End-to-end connect verified |
| M4 summon | Built 2026-10-28. rules/units.py, unit_card schema and filters, Spark detector with repair, SAM segmenter, signatures, tap fallback, re-roll, rename, Summon and UnitCard screens |
| M5 sprites and cost | Built 2026-10-28. Sprite pipeline, Muse Image generator, cache, style anchor, background push, dev credit meter, hard stop turns Demo Safe on. Asset script `backend/smoke/assets.py` waits on the key |
| M6 tracking and re-anchor | Built 2026-10-28. KCF TrackerSet (31.9 ms for 12 objects), freeze on loss, between-turn recovery, re-anchor ladder, live poses on the board |
| M7 and M8 rules, turn loop, enemies | Built 2026-10-28. Rules engine (99% coverage, E7 100%, 1.1 ms resolve), 15-state machine, night session with claim, tap intents, End Turn re-anchor, autosave, Night HUD, Sunrise, Defeat |
| M9 GM narration | Built 2026-10-28. Line bank (19 moments), gm_turn schema, SparkNarrator with repair and safety checks, background NarrationService with 20 s timeout, captions on Night, Sunrise and Defeat. Players sent as P1 to P4, `store` false |
| M10 safety | Built 2026-10-28. Delete campaign (rows, files, orphan sprites), autosave restore at the saved turn (schema v2 `night.board_json`), Demo Safe module with SAM re-anchor toggle, pause, camera check at End Turn, 60 s claim timeout, renderer controls |
| M11 voice | Built 2026-10-28. Taglish grammar, realtime DIARIZATION night session, live captions, voice chips with spoken cancel and End Turn, push-to-talk, voice off in Demo Safe and while paused. Live run Manual: EHIBE (key, mic). MVP scope complete offline |
| Phase 12 physical enemies and voice claim | Built 2026-10-29. Tikbalang push and throw, duwende steal, flee, return and escape in the rules engine, PHYSICAL_EFFECTS wait with ghosts, marks, badges and Done, voice claim with ako si and hawak ko. Table run Manual: EHIBE |
| Phase 13 code | Built 2026-10-29. Per-player recording consent, ffmpeg recorder (tested with a fake process), REC dot, narration logging, eval runner `eval/run_eval.py`. E7 50 of 50 (100%). ffmpeg, live evals, freeze tag and Playtest 2 are Manual: EHIBE |
| Phase 14 replay | Built 2026-10-29. Highlights, 10 FPS proxy, Files upload with expiry and delete, one SAM video request, reel render with sprites, damage numbers and dawn title card, anchor box fallback, Make Replay and Show in folder controls. Real reel needs ffmpeg and the key |
| Phase 15 code side | Done 2026-10-29. Root README with real numbers only, secret scan of history and tree (no secrets, one fake test key), raw video and voice audio ignored, summon how-it-was-made panel with model names, re-anchor flash, ffmpeg notice, `eval/run_eval.py cost`, final docs and demo audits. Video, license, freeze tag and submission are Manual: EHIBE |
| UI redesign | Done 2026-10-31. First-run Filipino or English pick, FIL / ENG toggle, one caption line per message, pixel night scene, JRPG windows, pixel icons, title-screen Start, short KeySetup, step-list Calibration, scene Sunrise and Defeat. Component CSS moved into `@layer components` |
| Finalization Phase 1 and 2 | Done 2026-11-03. ADR-0111 and ADR-0112, run command fixed, `DESKTOP_FFMPEG` passed to the backend, `null` origin only when packaged (`DESKTOP_PACKAGED`), electron-vite temp bundles ignored, P08 off Charm and Scout, `@electron-toolkit/preload` removed, CI workflow added |
| Finalization Phase 4 | Built 2026-11-03. WebAudio sound cues with a mute switch (`lib/sound.ts`, `desktop.sound`), first-night hints turns 1 to 3 (`lib/tutorial.ts`, `desktop.tutorial`), folklore glossary from Start and pause, P1 to P4 speaker chip. Copy reviews by Filipino players pending |
| Full audit | Done 2026-11-03 by seven agents (security, privacy and cost, correctness, checks, demo readiness, docs, cultural). No critical or high code findings. Fixed: spawn error crash, symlinked recordings folder, generic notice for unexpected errors, replay cleared on quit, cancelled paid calls charged, Connecting stall message, Calibration rescan, honest model labels, glossary focus, push-to-talk in dialogs, hint slot shift, cultural copy fixes, LICENSE added. Open: Tagalog glossary text, live evals and playtests |
| Post-freeze features | Built 2026-11-04 by EHIBE's call (ADR-0113). Kapre smoke with P08 back on Charm and Scout, Lost detection, barrio level, badges and scars, returning objects, Kagabi recap, Spark fallback parser, strict ownership, generated barrio map, optional Muse Glimmer recap (local Ollama, `DESKTOP_GLIMMER_URL`), Settings screen, Quit from pause, Back from Calibration. Schema v3 (additive). 16 states. Live checks Manual: EHIBE |
| Phase 6 release zip | Done 2026-11-04. `npm --prefix app run dist:win`, portable Python copied from the base 3.13 install (`app/scripts/stage-backend.mjs`), fuses on, `release/DeskTop-1.0.0-win.zip` 327.1 MB. Packaged app connects, saves settings and closes cleanly. Not yet run on a machine without Python |

## Superseded values

| Row | Old value | Current value | Source |
|---|---|---|---|
| M7 and M8 | 15-state machine | 16 states after ADR-0113 | `backend/game/state_machine.py` |
| Finalization Phase 1 and 2 | P08 off Charm and Scout | P08 back on both lists | ADR-0113 |
| M6 tracking and re-anchor | 31.9 ms for 12 KCF trackers | 34.7 ms median, 2026-11-04 | `backend/tests/test_tracker.py` benchmark |
| M7 and M8 | 1.1 ms resolve | 0.4 ms median, 2026-11-04 | `backend/tests/test_resolve.py` perf test |
| Phase 6 release zip | 327.1 MB | 323.8 MB (339,507,320 bytes), measured 2026-11-04 | `docs/delivery/release-and-packaging.md` |

## Next

Current state and the pending queue: `CLAUDE.md`. Results: `docs/eval.md` and `docs/playtests.md`.
