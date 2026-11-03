---
title: Judging scorecard
purpose: Criterion-by-criterion scorecard with evidence, gaps, finalization tasks and the video moment that proves each point
read_when: [prioritizing the last days before submission, planning video shots, final review]
canonical_for: [judging scorecard, model to workflow map, finalization tasks per criterion]
sources: [docs/market/judging-strategy.md, docs/market/positioning-and-messaging.md, docs/product/goals-and-metrics.md, docs/delivery/video-script.md, docs/eval.md, README.md]
status: active
last_verified: 2026-11-03
related: [docs/delivery/submission-text.md, docs/delivery/submission-checklist.md, docs/delivery/demo-runbook.md, docs/rules-notes.md]
---

# Judging scorecard

This page scores DeskTop against the four assumed judging criteria, lists the evidence in the repo today, the gaps, and the finalization tasks that close each gap. Baseline scores come from `docs/market/judging-strategy.md`. Nothing here is a new measurement.

## Key facts

| Fact | Value |
|---|---|
| Weights | Impact 30, Use of Meta AI Tooling 25, Demo Quality 25, Technical Depth and Execution 20. Assumed, not yet recorded from the Official Rules (A1). Verify in `docs/rules-notes.md` |
| Baseline total | 81.75 of 100 (as specified). Canonical: `docs/market/judging-strategy.md` |
| Target total | 88.25 of 100 |
| Video | Max 3:00 assumed. The script is extended to about 2:50. Canonical: `docs/delivery/video-script.md` |
| Freeze | New features end Nov 3 6:00 PM SGT. Fixes, packaging, docs and video until Nov 4 11:00 PM SGT |
| Evals recorded | E7 only (50 of 50, 2026-10-29). E1 to E6 not run. Canonical: `docs/eval.md` |

## Score summary

| Criterion | Weight | Baseline | Target | Main lever |
|---|---|---|---|---|
| Impact | 30 | 7 | 8 | Real Filipino friends playing on camera, named user |
| Use of Meta AI Tooling | 25 | 9 | 9.5 | Live proof of the four multi-step workflows, replay reel |
| Demo Quality | 25 | 8.5 | 9 | Packaged zip, crash-free dry runs, 3:00 video |
| Technical Depth and Execution | 20 | 8.5 | 9 | Real eval numbers, CI workflow, fuses, graceful recovery shown |

Targets are goals. They are reached only if the finalization tasks below are done and shown.

## Model to workflow map

Each model sits inside a multi-step workflow where code between the calls does real work. Canonical for the call contracts: `docs/architecture/meta-api-integration.md`.

| Workflow | Step 1 | Step 2 | Step 3 | Step 4 | Models used |
|---|---|---|---|---|---|
| Summon | Muse Spark 1.3 detects the object and returns a box | SAM 3.1 cuts the exact mask from that box | Muse Image 1.0 redraws the crop as a 16-bit sprite in the shared style | Muse Spark 1.3 writes the unit card from fixed enums | Spark, SAM, Image |
| Turn | Local KCF tracker follows objects between turns | SAM 3.1 re-anchors every piece at End Turn | Local rules engine resolves every number | Muse Spark 1.3 narrates from the resolved events, with a local line after 20 s | SAM, Spark |
| Voice | Muse Voice Transcribe 1.0 streams Taglish with speaker labels (diarization) | Local grammar maps text to command enums | Local rules engine checks and resolves the command | Chips show the order before it happens | Voice Transcribe |
| Replay | Files API upload of the 10 FPS proxy clip (with consent, expires in 24 h) | SAM 3.1 video request tracks objects across the night | Local ffmpeg render pins sprites, damage numbers and the dawn title card | Delete the upload | SAM, Files |

Code paths: `backend/vision/` (summon, SAM, sprites), `backend/gm/` (narrator), `backend/voice/`, `backend/replay/`, `backend/rules/`, `backend/meta_client.py`.

## Impact (weight 30)

| Item | Detail |
|---|---|
| What judges look for | Real-world utility, daily value, scalability, fit with the theme Build for Your World |
| Evidence today | Positioning and named users: `docs/market/positioning-and-messaging.md`. Personas: `docs/product/personas-and-jobs.md`. Filipino folklore, Taglish and English captions in the copy deck. Needs only a laptop, a webcam and an A4 sheet (`README.md`). Cultural care notes: `docs/design/cultural-care.md` |
| Gaps | No footage of real friends playing. No playtest quotes yet (`docs/playtests.md`). Folklore glossary not in the app. First-time players have no in-game hints. Taglish lines wait for playtester review. Market evidence on group play habits is thin |
| Finalization tasks | Film real players with written OK. Add the in-app folklore glossary and first-night tutorial hints (approved for Nov 3). Record playtest notes as a small sample, labeled. Ship the packaged zip so a judge can try it without a dev setup |
| Video proof | Hook and shared-table shots, current script 0:00 to 0:20. The night shots, 0:55 to 1:35. Title card at the end. Timestamps may shift in the extended script |
| Risk | R12: judges may discount a game on Impact. Lead with the shared-table problem and real players |

## Use of Meta AI Tooling (weight 25)

| Item | Detail |
|---|---|
| What judges look for | Meta models in core logic and multi-step workflows, not a chat wrapper |
| Evidence today | All four models wired through one client with timeouts, retries, breaker and cost meter (`backend/meta_client.py`). Smoke scripts for each model in `backend/smoke/`. Recorded fixtures drive offline tests. Strict schemas for unit cards and GM turns. Workflow table above. How-it-was-made panel on the summon screen names the models |
| Gaps | No live run of the full Muse pipeline has been recorded. Some live response shapes (voice events, SAM video records) are coded from docs and need a recorded fixture (`README.md`, Known limits). E5 sprite acceptance not rated. Real replay reel not yet rendered with the key |
| Finalization tasks | Run the smoke scripts and the asset script with the key, EHIBE watching, inside the $15 live budget. Record a DIARIZATION fixture. Render one real replay reel. Run E1 and E5 and record real numbers in `docs/eval.md`. Show model names on screen when each acts |
| Video proof | Summon split screen of Spark box, SAM mask, Muse Image sprite (current script 0:20 to 0:45). Voice claim with speaker chips (0:45 to 0:55). Replay reel (1:50 to 2:05) |

## Demo Quality (weight 25)

| Item | Detail |
|---|---|
| What judges look for | Deterministic, crash-free live reliability. A seamless journey. A compelling 3-minute video |
| Evidence today | Demo Safe Mode plays a full night offline. Autosave restore at the saved turn. 20 s narration timeout with a local line. Rules engine is deterministic (E7, 50 of 50). Runbook: `docs/delivery/demo-runbook.md`. UI redesign done 2026-10-31 |
| Gaps | KeySetup, Calibration, Night, Sunrise and Defeat have not been seen in the running app. No packaged build. No sound. Zero crash-free dry runs logged. No video footage. Speaker chip not built |
| Finalization tasks | Build the unsigned Windows zip with the backend bundled, then test it on a clean path. Add code-synthesized sound effects (WebAudio). Add the speaker chip. Run the Playtest 1 checklist and three consecutive clean runs before recording. Record the video to the script. Keep a backup recording |
| Video proof | Hook in the first 8 seconds. Full night (current script 0:55 to 1:35). Manananggal split (1:35 to 1:50). Sunrise (1:50 to 2:05). No cuts hiding failures |
| Rule | 0 crashes in the last 3 runs before recording (`docs/product/goals-and-metrics.md`) |

## Technical Depth and Execution (weight 20)

| Item | Detail |
|---|---|
| What judges look for | Sound architecture, graceful recovery, edge-case resilience, production code quality |
| Evidence today | Pure rules engine owns every number (`backend/rules/`). Hybrid tracking with re-anchor ladder. Token-gated backend on 127.0.0.1, key in safeStorage. Cost meter with hard stop. Schema v2 with stepped migration. Tests, ruff, mypy --strict, tsc, eslint and prettier clean. Test count: [MEASURED: re-read from the test run on submit day] (1,229 on 2026-11-03). E7 50 of 50. Rules resolve 1.1 ms median, tracker 31.9 ms median (`README.md`) |
| Gaps | No CI. No Electron fuses. No Python dependency audit (known gap, accepted). Packaged build has known path and Origin bugs to fix. E1 to E6 not run. No troubleshooting guide |
| Finalization tasks | Add the GitHub Actions workflow (tests, ruff, mypy, typecheck, lint). Set fuses through the electron-builder `electronFuses` config. Fix the code-check bugs listed in the shared brief. Run E1, E2, E4, E6 and record real numbers. Write a troubleshooting section for judges in `docs/how-to-run.md`. State the Python audit gap honestly |
| Video proof | Under-the-hood shot with architecture, hybrid tracking, rules engine, eval numbers and cost per night (current script 2:05 to 2:20). Show only numbers from `docs/eval.md` |

## Finalization task list

| Task | Closes gap in | Owner |
|---|---|---|
| Pre-built unsigned Windows zip with bundled backend | Demo, Technical | Build, then EHIBE verifies |
| Live Muse pipeline proof (smoke, assets, one reel) | Tooling | EHIBE with key |
| E1, E5, E6 real numbers in `docs/eval.md` | Tooling, Technical | EHIBE and test runner |
| Code-synthesized sound effects | Demo | UI work, before 6:00 PM freeze |
| In-app folklore glossary | Impact | UI work, before freeze |
| First-night tutorial hints | Impact, Demo | UI work, before freeze |
| Speaker chip | Demo, Tooling | UI and voice work, before freeze |
| GitHub Actions workflow | Technical | Docs and config, EHIBE pushes |
| Electron fuses via `electronFuses` | Technical | Config |
| Troubleshooting section | Demo, Technical | Docs |
| Real-player footage with written OK | Impact | EHIBE |

## Unverified items

| Item | Verify by |
|---|---|
| Criterion names and weights | Read the Official Rules into `docs/rules-notes.md`, then rescore within 24 h |
| Video length cap and whether the repo must be public | Same step |
| Current self-scores | They are plan estimates, not judge feedback. Rescore after the dry runs |
