---
title: Finalization plan
purpose: Ordered, time-boxed roadmap that takes DeskTop from MVP-complete to a submitted, production-ready, judge-winning build
read_when: [start of any finalization work, choosing the next task, before the freeze, before submitting]
canonical_for: [finalization steps, finalization owners, finalization acceptance checks, Nov 3 to Nov 5 task order]
sources: [CLAUDE.md, docs/prompts/FEATURE_PROMPT.md, docs/delivery/schedule.md, docs/delivery/judging-scorecard.md, docs/market/judging-strategy.md, docs/delivery/demo-runbook.md, docs/delivery/submission-checklist.md]
status: active
last_verified: 2026-11-03
related: [docs/delivery/release-and-packaging.md, docs/delivery/live-api-runbook.md, docs/delivery/submission-text.md, docs/product/user-journey.md, docs/design/onboarding-and-tutorial.md, docs/engineering/troubleshooting.md]
---

# Finalization plan

This plan turns the MVP-complete build into a finished game that a judge can unzip, play and understand, with live Meta models in every core workflow. Work runs in the order below, each step has an owner, a criterion it raises, a check that proves it, and a commit.

## Key facts

| Fact | Value |
|---|---|
| Plan written | 2026-11-03, about 1:00 PM SGT |
| Feature freeze | Nov 3, 6:00 PM SGT. New features stop. Fixes, packaging, docs and video continue |
| Internal submit | Nov 4, 11:00 PM SGT |
| Hard deadline | Nov 5, 10:00 AM SGT |
| Judging weights (assumed, A1) | Impact 30, Use of Meta AI Tooling 25, Demo Quality 25, Technical Depth 20 |
| Baseline self-score | 81.75. Target 88.25. Canonical: `docs/delivery/judging-scorecard.md` |
| Live spend budget today | $15 on top of what api_usage already shows. Hard stop stays at $120 |
| Working prompt | `docs/prompts/FEATURE_PROMPT.md` |
| Owners | Claude (code, docs, scripted checks) and EHIBE (key, table, camera, people, video, push, submit) |

## Decisions locked on 2026-11-03

EHIBE answered "all defaults" to the 31 discovery questions. These are binding for this plan.

| # | Decision |
|---|---|
| D1 | The freeze holds at Nov 3 6:00 PM SGT for new features |
| D2 | Production ready means a pre-built, unsigned Windows zip with the Python backend bundled |
| D3 | Build today: code-made sound cues, folklore glossary, first-night tutorial hints, speaker chip. Skip Settings |
| D4 | Campaign progression F16 is cut |
| D5 | P08 Liwanag leaves the Charm and Scout power lists while Kapre smoke is cut |
| D6 | EHIBE pastes the key in KeySetup and types it into `backend/.env`. Claude never reads that file |
| D7 | Live budget today is $15. Claude may run smoke and asset scripts with EHIBE watching |
| D8 | Contributor mode off is confirmed by EHIBE in the dashboard |
| D9 | Assume the Official Rules: weights above, 3:00 video max, public repo |
| D10 | Extend the video script to about 2:50 |
| D11 | Player count reads 1 to 4 everywhere |
| D12 | License: MIT for code, CC BY-NC 4.0 for original assets |
| D13 | Friends film tonight with written OKs |
| D14 | ffmpeg via `winget install Gyan.FFmpeg`, run by EHIBE |
| D15 | EHIBE is at the table for camera work. Claude drives the app over CDP for screenshots |
| D16 | Claude may create and then delete a throwaway campaign for screenshots |
| D17 | B12 fuses through electron-builder `electronFuses`. B13 remove `@electron-toolkit/preload`. B15 approved and closed |
| D18 | Fix every bug the code check found |
| D19 | No pip-audit. Record it as a known gap |
| D20 | Add a GitHub Actions workflow file. EHIBE pushes |
| D21 | Prompts live in `docs/prompts/`, old ones in `docs/prompts/archive/`. This plan lives here |
| D22 | Commits: `type: Action item`, no ticket ID, EHIBE sole author, no trailers, as many as needed |
| D23 | EHIBE tags `freeze-nov3` and pushes. Agents run on Sonnet 5.5 at medium effort, one writer per file |
| D24 | Visual direction stays: Gabi 16, Press Start 2P, NightScene, JRPG windows |

## Gate 0: approval

- [x] EHIBE approves this plan and the new docs. Nothing in Phase 1 onward starts before that. Approved 2026-11-03 with all defaults.

## Phase 1: docs and decisions (Claude, 1:30 PM to 2:00 PM)

Raises Technical Depth. Every later step reads these files.

Status: Done 2026-11-03. All four steps committed. desktop-docs-keeper drift findings applied.

| Step | Task | Check | Commit |
|---|---|---|---|
| 1.1 | Add ADR-0111 packaged build and origin, ADR-0112 finalization scope (D3, D4, D5, D19) | Index row in `docs/decisions/README.md` | `docs: Record the packaging and finalization scope decisions` |
| 1.2 | Fix the backend run command everywhere it is wrong (`CLAUDE.md`, `setup-windows.md`). Keep PRD and Build Guide unchanged as history | grep finds no `server:app` outside history files | `docs: Correct the manual backend run command` |
| 1.3 | Update CLAUDE.md: state date, B13 to B15 closed or done, B14 only ffmpeg, docs map, prompt path, plan link, pending queue from this plan | desktop-docs-keeper finds no drift in CLAUDE.md | `docs: Point CLAUDE.md at the finalization plan` |
| 1.4 | Reconcile drift found in discovery: player count 1 to 4, E3 done-when 43 of 50 for 85%, cut order, freeze date note, env var table, preload surface in ADR-0103, CSP port line | desktop-docs-keeper report clean on those items | `docs: Fix drift in counts, targets, env vars and preload notes` |

## Phase 2: code fixes (Claude, 2:00 PM to 3:00 PM)

Raises Demo Quality and Technical Depth. Each fix gets a test where the stack allows it.

Status: Done 2026-11-03. All six steps committed. Extra fix: three tests read content filter lists relative to the working directory and failed from the repo root. They now read from `gm.schemas.DATA_DIR`. 1229 tests pass from the repo root and from `backend`. CI waits on EHIBE's push.

| Step | Task | Owner agent | Check | Commit |
|---|---|---|---|---|
| 2.1 | Pass `DESKTOP_FFMPEG` through `PASSTHROUGH_ENV` in `app/src/main/backend.ts` | desktop-ui-engineer | typecheck, lint, a run with the var set finds ffmpeg | `fix: Pass the ffmpeg path setting through to the backend` |
| 2.2 | Accept the packaged renderer origin. Allow `null` only when main marks the build packaged, token still required | main session | pytest for null allowed when packaged, refused in dev, token still required | `fix: Accept the packaged renderer origin while keeping the token check` |
| 2.3 | Ignore electron-vite temp `*.mjs` files in `app/.gitignore` and delete the stray one | main session | `git status` clean of it | `chore: Ignore electron-vite temp config bundles` |
| 2.4 | Remove P08 from Charm and Scout lists, adjust clamp fallback, tests and game docs | desktop-rules-engineer | pytest green, E7 100%, coverage 90%+ | `feat: Drop Liwanag from power lists while kapre smoke is cut` |
| 2.5 | Remove unused `@electron-toolkit/preload` (approved dependency change) | main session | `npm --prefix app ls`, typecheck, build | `chore: Remove the unused preload toolkit dependency` |
| 2.6 | Add `.github/workflows/ci.yml`: Windows runner, Python 3.13, pytest, ruff, mypy strict, npm ci, typecheck, lint | main session | YAML parses. First real run after EHIBE pushes | `chore: Add a CI workflow for tests, types and lint` |

## Phase 3: go live with Muse (EHIBE and Claude, 2:00 PM to 3:30 PM, runs alongside Phase 2)

Raises Use of Meta AI Tooling and Demo Quality. Procedure and stop rules: `docs/delivery/live-api-runbook.md`.

| Step | Task | Owner | Check |
|---|---|---|---|
| 3.1 | Claim credits, confirm Contributor mode off, read Official Rules, fill `docs/rules-notes.md` answers | EHIBE | Rules table filled. A1, A2, A4, A15 updated |
| 3.2 | Paste the key in KeySetup and type it into `backend/.env` | EHIBE | KeySetup shows saved |
| 3.3 | Run the Phase 1 smoke scripts in runbook order | Claude runs, EHIBE watches | Each result row in `rules-notes.md`, A6 resolved |
| 3.4 | Run `python -m smoke.assets --date 2026-11-03` for placeholder and enemy art | Claude | Files in `assets/sprites/enemies` and `placeholders`, cost logged |
| 3.5 | Rate 20 sprites for E5 | EHIBE | `docs/eval.md` E5 row from real ratings |
| 3.6 | Check spend with `eval/run_eval.py cost` | Claude | Under budget, recorded |

Commits: `docs: Record live smoke results and official rules answers`, `feat: Add generated enemy and placeholder sprites`.

## Phase 4: game feel features (Claude, 3:00 PM to 5:30 PM, before the freeze)

Raises Demo Quality and Impact. Spec: `docs/design/onboarding-and-tutorial.md`. Every new line goes through desktop-add-copy-key and desktop-cultural-reviewer.

| Step | Task | Check | Commit |
|---|---|---|---|
| 4.1 | Sound cues made with WebAudio: ambience, spawn gong, End Turn bell, hit, dodge, sunrise chime, defeat tone. Mute toggle saved locally. Never the only signal | Heard in a run, mute works, reduced-motion untouched, no files added | `feat: Add code-made sound cues with a mute toggle` |
| 4.2 | First-night tutorial hints for turns 1 to 3, shown once per campaign, dismissible | Shows on a new campaign, not on Continue, FIL and ENG fit | `feat: Teach the first night with short turn hints` |
| 4.3 | Folklore glossary panel from Start and Night pause, 8 terms | Opens and closes by tap and keyboard, cultural review passed | `feat: Add an in-game folklore glossary` |
| 4.4 | Speaker chip P1 to P4 with colour and shape | Shows the active speaker in a voice night, no real names sent out | `feat: Show who is speaking with a speaker chip` |
| 4.5 | Copy deck, screens, HUD and requirements-index synced | desktop-docs-sync done | `docs: Sync design docs after the game feel features` |

At 5:30 PM, anything not done in Phase 4 is cut, not rushed.

## Phase 5: look at every screen (Claude, 5:00 PM to 6:00 PM)

Raises Demo Quality. Uses CDP screenshots per `docs/delivery/handoff-ui-redesign.md`.

- [ ] Screenshot KeySetup, Calibration, Summon, UnitCard, VoiceClaim, Night, Sunrise and Defeat in FIL and ENG.
- [ ] Fix text overflow, two-line buttons and the Sunrise and Defeat score panel overlap.
- [ ] Run the impeccable audit on the Night HUD.
- [ ] Delete the throwaway campaign and check the data folder.
- Commit: `fix: Fit every screen in Filipino and English at 1920x1080`.

## Freeze: Nov 3, 6:00 PM SGT

- [ ] All tests, mypy, ruff, typecheck, lint, prettier and npm audit pass. Results recorded.
- [ ] EHIBE runs `git tag freeze-nov3` and pushes.

## Phase 6: packaged zip (Claude, 6:00 PM to 8:30 PM)

Raises Demo Quality and Technical Depth. Canonical steps: `docs/delivery/release-and-packaging.md`.

| Step | Task | Check |
|---|---|---|
| 6.1 | electron-builder `extraResources` for the backend and its venv, `zip` target, `electronFuses` set | Config builds |
| 6.2 | Build, unzip into a clean folder, first run, KeySetup, Demo Safe night with Wi-Fi off | Night finishes. Backend log has no secrets |
| 6.3 | Record zip size and SHA-256 in the release doc | Real numbers only |

Commit: `feat: Ship a Windows zip with the backend bundled and fuses on`.

## Phase 7: playtests, evals and demo night (EHIBE with Claude, Nov 3 evening)

Raises every criterion with real evidence. Procedure: `docs/delivery/demo-runbook.md`.

- [ ] ffmpeg installed (D14).
- [ ] Playtest 1: Demo Safe night with Wi-Fi off, kill at turn 5, resume, delete a test campaign.
- [ ] Table run with a tikbalang push and a duwende steal.
- [ ] Two consented live nights with friends. Collect written OKs first.
- [ ] Run `eval/run_eval.py e4 --db`, `e6 --db` and `cost`. Record E1 to E3 data. Real numbers into `docs/eval.md`.
- [ ] Make the replay, open it in Windows Media Player, check sprites stay on objects.
- [ ] Fun rating and "would you post this" answers into `docs/playtests.md`.
- [ ] Copy all footage to two drives.

## Phase 8: video, README, license, submit (EHIBE with Claude, Nov 4)

Raises Demo Quality and Impact.

| Step | Task | Owner |
|---|---|---|
| 8.1 | Extend `docs/delivery/video-script.md` to about 2:50 with the live model pipeline shot | Claude |
| 8.2 | Record and edit the video, captions burned in | EHIBE |
| 8.3 | Add `LICENSE` (MIT) and the asset license note | Claude |
| 8.4 | README: measured numbers, demo GIF, video link, zip link | Claude drafts, EHIBE adds links |
| 8.5 | Fill `docs/delivery/submission-text.md` placeholders with measured numbers | Claude |
| 8.6 | Secret scan of tree, history and the zip | Claude |
| 8.7 | Push public, attach the zip to a GitHub release, submit by Nov 4 11:00 PM SGT, save the confirmation | EHIBE |

## Cut order if time runs short

1. Speaker chip (4.4).
2. Glossary (4.3).
3. CI workflow (2.6).
4. Zip packaging falls back to the from-source guide in `docs/how-to-run.md`.

Never cut: the fixes in Phase 2.1 and 2.2, live smoke runs, the Demo Safe night, real eval numbers, the video, the submission.

## Risks for today

| Risk | Response |
|---|---|
| Live call fails with 401 or 403 | Stop, check the key and credits, keep building offline |
| Spend climbs | Stop at the $15 day budget, Demo Safe on |
| Bundled venv too large or fails on a clean folder | Ship the from-source guide, record the gap honestly |
| A new feature slips past 5:30 PM | Cut it per the cut order |
| Camera or mic fails tonight | Demo Safe with taps, then the backup recording |

## Done when

- A judge can unzip, run, pick a language, play a Demo Safe night offline and a live night online without a raw error.
- All four Meta models appear on screen in real workflows, with measured numbers in the README.
- Tests, types, lint and audit are clean. Docs match the code. The video is submitted before Nov 4 11:00 PM SGT.
