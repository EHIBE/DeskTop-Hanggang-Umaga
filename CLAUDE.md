# CLAUDE.md: DeskTop: Hanggang Umaga

Project memory for AI agents. Read this first, then `docs/README.md`, then the one topic file you need. The master working prompt is `docs/FEATURE_PROMPT.md`.

## Project

- Windows desktop game. A top-down webcam turns real desk objects into 16-bit pixel art units. 1 to 4 players at one table move objects by hand and give Taglish voice orders. Filipino folklore creatures attack for 8 turns until sunrise.
- Solo build by EHIBE for the Meta Global AI Developer Hackathon 2026, Indie track, theme Build for Your World.
- Stack: Electron + React + TypeScript renderer (`app/`), FastAPI + OpenCV + SQLite backend on 127.0.0.1 (`backend/`), four Meta models (Muse Spark 1.3, SAM 3.1, Muse Image 1.0, Muse Voice Transcribe 1.0).

## State

| Item | Status (2026-10-28) |
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
| Tests | 1219 backend passing. ruff, mypy --strict, typecheck, lint, prettier clean |
| CI, git hooks | None |

## Pending queue

Ordered. Canonical schedule: `docs/delivery/schedule.md`.

1. Manual: EHIBE. Official Rules answers, credits, `MODEL_API_KEY` in `backend/.env`, Contributor mode off (`docs/rules-notes.md`)
2. Manual: EHIBE. Run the Phase 1 smoke scripts (`docs/rules-notes.md` runbook)
3. Manual: EHIBE. Look at the window: KeySetup or Start, then Calibration with the real camera (feed at 20 FPS+, 4 corner taps, ruler check)
4. Manual: EHIBE. Install ffmpeg on PATH before Phase 13
5. Manual: EHIBE. Run `backend\.venv\Scripts\python -m smoke.assets --date <today>` from `backend` for placeholder and enemy art, then rate sprites (E5)
6. Manual: EHIBE. Voice smoke script, then a spoken night (captions, chips, "hindi", "tapos na", hold Space) and record a DIARIZATION fixture so the event field names are verified
7. Manual: EHIBE. Play a Demo Safe night with Wi-Fi off, kill the app at turn 5 and resume, delete a test campaign and check `%APPDATA%\DeskTop` (Playtest 1)
8. Manual: EHIBE. Play a night with a tikbalang push and a duwende steal on the real table (turn 3 on Normal teaches the push)
9. Manual: EHIBE. Install ffmpeg, play two consented nights, run `eval/run_eval.py e4 --db` and `e6 --db` on the database, record E1 to E3 data, then the freeze tag (`git tag freeze-nov3`, push) at Nov 3 6:00 PM SGT and Playtest 2
10. Manual: EHIBE. After a consented night, tap Make the Replay, open the reel in Windows Media Player and check sprites stay on objects (FR-47 90%)
11. Manual: EHIBE. Choose the license, add the demo GIF and video link to README.md, record the video per docs/delivery/video-script.md, push the repo public, submit by Nov 4 11:00 PM SGT and save the confirmation

## Constraints

- Rules engine owns every number. Models choose from enums and narrate only.
- Backend binds 127.0.0.1 only and checks a per-launch token on every request.
- API key lives in Electron safeStorage. Never in the renderer, logs, repo, or docs.
- Standard mode on every Meta call. Never Contributor mode.
- Cost meter: warn at $90, hard stop paid calls at $120.
- Tests run offline on recorded fixtures. No paid calls in tests.
- No new dependencies, destructive commands, or schema changes on a live DB without approval.
- Zero code comments in new code. No debug code.
- All agents run on Sonnet 5.5 (`claude-sonnet-5-5`) at medium effort.
- Commits: auto-commit allowed on main. Format `type: Action item`. EHIBE is the sole author. No co-author trailers, no AI attribution. No push, merge, rebase, reset, stash, checkout, branch, tag, or amend.
- Never read `backend/.env`.
- Doc prose: no semicolons, no em dashes.
- Feature freeze Nov 3 6:00 PM SGT. Submit by Nov 4 11:00 PM SGT. Hard deadline Nov 5 10:00 AM SGT.

## Bugs and contradictions

Each has a Proposed ADR in `docs/decisions/`.

| ID | Issue | ADR |
|---|---|---|
B11 (fixed port) closed in M3. B1 to B10 resolved 2026-10-28 (ADR-0101 to ADR-0110 accepted, B1, B2, B3, B6 code paths, B7 and B8 fixed in M0).

| ID | Open issue | Owner |
|---|---|---|
| B12 | No Electron fuses (RunAsNode, ASAR integrity). Needs `@electron/fuses`, a new dependency | Approval: EHIBE |
| B13 | `@electron-toolkit/preload` unused since ADR-0103. Removal is a dependency change | Approval: EHIBE |
| B14 | Python 3.11 not installed, venv uses 3.13. ffmpeg not on PATH | ADR-0101, Manual: EHIBE |
| B15 | Schema v2 adds `night.board_json` with a stepped migration so restore is exact. data-model.md asks for approval on schema changes | Approval: EHIBE |

## Commands

Run from repo root.

| Task | Command |
|---|---|
| Test | `backend\.venv\Scripts\python -m pytest backend/tests -q` |
| Single test | `backend\.venv\Scripts\python -m pytest backend/tests/test_resolve.py::test_name -q` |
| Typecheck | `npm --prefix app run typecheck` |
| Lint | `npm --prefix app run lint` |
| Format | `npm --prefix app run format` |
| Audit | `npm --prefix app audit` |
| Run app | `npm --prefix app run dev` |
| Run backend | `cd backend` then `.venv\Scripts\python -m uvicorn server:app --host 127.0.0.1 --port 8765` |
| Python lint | `cd backend` then `.venv\Scripts\python -m ruff check .` |
| Python types | `cd backend` then `.venv\Scripts\python -m mypy --strict --exclude .venv .` |
| Python audit | NONE configured |

## Docs map

| Need | File |
|---|---|
| Doc index and read order | `docs/README.md` |
| Terms | `docs/glossary.md` |
| What to build | `docs/DeskTop_PRD.md`, `docs/product/` |
| Requirement status | `docs/product/requirements-index.md` |
| Game rules | `docs/game/` |
| Visual design | `docs/design/DESIGN.md` |
| Architecture and contracts | `docs/architecture/` |
| Setup, standards, tests, security | `docs/engineering/` |
| Schedule, risks, demo | `docs/delivery/` |
| Market and judging | `docs/market/` |
| Decisions | `docs/decisions/` |
| How to build, by phase | `docs/DeskTop_Build_Guide.md` |

## Agents

All on Sonnet 5.5, medium effort. Files in `.claude/agents/`.

| Agent | Use for |
|---|---|
| desktop-rules-engineer | `backend/rules` and its tests |
| desktop-vision-engineer | Capture, calibration, tracker, SAM, Spark detection, sprites |
| desktop-voice-engineer | Realtime voice, grammar, voice claim |
| desktop-gm-contract-engineer | Prompts, schemas, validation, line bank |
| desktop-ui-engineer | Renderer screens, HUD, canvas, copy |
| desktop-electron-security-reviewer | Read-only Electron and token review |
| desktop-privacy-cost-auditor | Read-only privacy, consent, cost review |
| desktop-cultural-reviewer | Read-only Taglish and folklore review |
| desktop-test-eval-runner | Run tests and evals, record real results |
| desktop-docs-keeper | Read-only docs drift audit |
| desktop-demo-readiness-checker | Read-only demo checklist audit |

## Skills

| Skill | Use for |
|---|---|
| desktop-add-power-or-enemy | Change powers, enemies, waves |
| desktop-add-meta-call | Add a Meta model call |
| desktop-add-copy-key | Add player-facing text |
| desktop-add-ws-message | Add a WebSocket message type |
| desktop-docs-sync | Update docs after any change |
| desktop-demo-safe-check | Verify offline and Demo Safe Mode behavior |
| impeccable, frontend-design | UI design and critique |
| dataviz | Eval and cost charts |
| security-review, code-review, simplify | Review before reporting |
| run | Launch the app to confirm a change |

## Decisions

Accepted: ADR-0001 to ADR-0012 and ADR-0101 to ADR-0110. ADR-0012 holds the MVP build defaults (damage with shields, walls, ties, fail-closed token). Proposed: none. Index: `docs/decisions/README.md`.
