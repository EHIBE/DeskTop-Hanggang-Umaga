---
title: Schedule
purpose: Current day-by-day plan, phases 0 to 15 with done-when and if-stuck lines, freeze and deadlines
read_when: [start of each day, planning work, a day slips]
canonical_for: [current schedule, phase list, freeze, deadlines, daily routine]
sources: [docs/DeskTop_Build_Guide.md#the-honest-schedule, docs/DeskTop_Build_Guide.md#daily-routine, docs/DeskTop_PRD.md#17-milestones-and-timeline]
status: active
last_verified: 2026-10-28
related: [docs/product/scope-and-cuts.md, docs/delivery/risk-register.md, docs/decisions/ADR-0109-schedule-source.md]
---

# Schedule

The Build Guide schedule replaces the PRD timeline (ADR-0109). The date is fixed and scope moves through the cut order in `product/scope-and-cuts.md`.

## Key facts

| Milestone | When (SGT) | UTC | ET |
|---|---|---|---|
| Build window opened | Oct 27, 01:00 AM | Oct 26, 17:00 | Oct 26, 12:00 PM |
| Feature freeze | Nov 3, 6:00 PM | Nov 3, 10:00 | Nov 3, 5:00 AM |
| Demo recording and Playtest 2 | Nov 3 evening | | |
| Internal submit target | Nov 4, 11:00 PM | Nov 4, 15:00 | Nov 4, 10:00 AM |
| Hard deadline | Nov 5, 10:00 AM | Nov 5, 02:00 | Nov 4, 9:00 PM |
| Judging | Nov 4 to Nov 8 | | |
| Finals | Nov 9 | | |
| Planned hours | 66.5 | | |

## Days

| Date | Hours | Phases | Must pass by end of day |
|---|---|---|---|
| Oct 27 (Tue) night | 1.5 | 0 | Tools installed, rules read, key works |
| Oct 28 (Wed) | 7 | 1, 2, 3 | Every API smoke test passes. Warped desk feed shows in the Electron window |
| Oct 29 (Thu) | 7 | 4, start 5 | 5 objects register with masks and unit cards |
| Oct 30 (Fri) | 7 | Finish 5, 6 | Sprites on objects. Sprites follow your hand. End Turn re-anchors |
| Oct 31 (Sat) | 10 | 7, start 8 | Rules tests green. A night runs through every state |
| Nov 1 (Sun) | 10 | Finish 8, 9, 10, Playtest 1 | Full 8-turn night by tap with narration |
| Nov 2 (Mon) | 8 | 11, 12 | Voice orders work. Tikbalang push and duwende steal work |
| Nov 3 (Tue) | 8 | 13, evals, fixes, freeze, Playtest 2 and demo recording | 3 crash-free nights. Raw footage saved twice |
| Nov 4 (Wed) | 8 | 14, 15 | Reel rendered. Video, README and submission done by 11:00 PM SGT |

## Phases

| Phase | Hours | Scope | Done when | If stuck |
|---|---|---|---|---|
| 0 Before code | 1.5 | Rules, credits, key, Standard mode, tools, physical setup, repo | Rules notes written, credits claimed, tools print versions, repo pushed | Re-scope same day if rules conflict |
| 1 API smoke tests | 1.5 | Venv, shared client, Spark structured output, SAM boxes, Muse Image, Voice, Files | All 5 smoke tests run, fixtures saved, sprite latency noted. Scripts built 2026-10-28, runs are Manual: EHIBE (key, inputs, two voices) | Ask in Discord office hours, move to Phase 2 |
| 2 Camera and calibration (F01) | 2 | Capture, A4 homography, ruler check, baseline | Warped feed square-on, ruler within 0.5 cm, calibration saved. Backend built and tested 2026-10-28. Square-on feed and ruler check on the real desk are Manual: EHIBE after M3 shows the feed | Raise camera, use a plain mat |
| 3 App shell (Tailwind, spawn, stream) | 3.5 | Electron scaffold, backend spawn with key and token, frame stream | Warped feed at 20 FPS+ in the window. Built 2026-10-28: spawn, socket and streaming verified end to end. On-screen FPS check with the real camera Manual: EHIBE | Check electron-vite and Tailwind docs |
| 4 Summon (F02) | 5 | Spark detect, SAM masks, clamp, caps, tap fallback | 5 objects with masks and cards, card in 8 s or less. Built 2026-10-28 with the offline tap path verified in tests. Live Spark and SAM runs and the 8 s timing are Manual: EHIBE (key, camera) | Make tap-to-select the main path |
| 5 Sprites (F03) and cost tracker (F18) | 4 | Placeholders and enemies first, pipeline, cache, api_usage | 10 objects get sprites, 8+ look right, every call logged. Pipeline, cache, background job, hard stop and dev meter built 2026-10-28. Asset run, 10 live sprites and the E5 rating are Manual: EHIBE | Pre-generate the 5 demo sprites |
| 6 Tracking and re-anchor (F04, F05) | 7 | Trackers, EMA, freeze, re-anchor ladder | 6 objects follow, re-anchor 20 of 20. Built and tested offline 2026-10-28. Real-desk follow and 20 of 20 are Manual: EHIBE (camera, key) | Drop look-alike objects from the demo |
| 7 Rules, loop, HUD (F06) | 6 | Rules engine, state machine, HUD, tests | Tests green, a night runs through every state | None |
| 8 Core enemies (F07) | 2 | Aswang, Manananggal, stats for the rest, waves | Full 8-turn night with all waves and arrows | None |
| 9 GM narration (F09) | 3 | System prompt, gm_turn, repair, line bank | Every turn shows a caption within 6 s or a line bank line | Line bank only |
| 10 Safety (F13, F14, F17, F24) | 5 | Tap controls, autosave, Demo Safe Mode, delete data, Playtest 1 | Whole night by taps, kill and resume at turn 5, Wi-Fi off night completes, no files remain | Fix rule bugs only |
| 11 Voice (F10) | 4 | Two sessions, audio loop, events, grammar, PTT | 40 of 50 test orders parsed | ENDPOINTING plus tap-to-claim |
| 12 Voice claim, physical enemies (F11, F08) | 4 | Claim, overlap, push, steal | Both effects work in a test night | Cut duwende steal first |
| 13 Recording, evals, freeze, demo | 8 | Consent, recorder, evals, fixes, freeze, Playtest 2 | 2 complete nights recorded, footage backed up | Crash and demo-visible fixes only |
| 14 Replay reel (F15) | 4 | Highlights, proxy, upload, SAM video, delete, render | 30 to 60 s reel from demo footage | Keep a 10 s clip, move on by 2:00 PM SGT |
| 15 Video, README, submission | 4 | Video, README, secret scan, submit | Submitted, confirmation saved | Submit what is done by Nov 5, 8:00 AM SGT |

## Freeze rules

- Gameplay feature freeze Nov 3 6:00 PM SGT. After it, only crash and demo-visible fixes.
- Replay pipeline on Nov 4 is the single exception, because it is post-processing on recorded footage.

## Daily routine

| When | Do |
|---|---|
| Start of day | Read today's row. Check credits used |
| Every 2 h | Commit (push only when EHIBE says) |
| End of day | Run pytest. Check the done-when line. Note slips. Apply the cut order the same day |
| Blocker over 45 min | Ask in Discord office hours, switch tasks |

## Status (update daily)

| Date | Planned | Actual | Notes |
|---|---|---|---|
| Oct 27 | Phase 0 | Scaffold commit 3379e9c | Phase 0 checklist not recorded in rules-notes.md |
| Oct 28 | Phases 1 to 3 | Docs, agents and skills added. M0 foundations done: venv on Python 3.13, Tailwind, Electron hardening, config, store, meta_client, 67 tests | Phase 1 smoke tests wait on Manual: EHIBE (key). ffmpeg is Manual: EHIBE before Phase 13 |
