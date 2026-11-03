# CLAUDE.md: DeskTop: Hanggang Umaga

Project memory for AI agents. Read this first, then `docs/README.md`, then the one topic file you need. The master working prompt is `docs/prompts/FEATURE_PROMPT.md`. The finalization roadmap is `docs/FINALIZATION_PLAN.md`.

## Project

- Windows desktop game. A top-down webcam turns real desk objects into 16-bit pixel art units. 1 to 4 players at one table move objects by hand and give Taglish voice orders. Filipino folklore creatures attack for 8 turns until sunrise.
- Solo build by EHIBE for the Meta Global AI Developer Hackathon 2026, Indie track, theme Build for Your World.
- Stack: Electron + React + TypeScript renderer (`app/`), FastAPI + OpenCV + SQLite backend on 127.0.0.1 (`backend/`), four Meta models (Muse Spark 1.3, SAM 3.1, Muse Image 1.0, Muse Voice Transcribe 1.0).

## State

| Item | Status (2026-11-03) |
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
| Full audit | Done 2026-11-03 by seven agents (security, privacy and cost, correctness, checks, demo readiness, docs, cultural). No critical or high code findings. Fixed: spawn error crash, symlinked recordings folder, generic notice for unexpected errors, replay cleared on quit, cancelled paid calls charged, Connecting stall message, Calibration rescan, honest model labels, glossary focus, push-to-talk in dialogs, hint slot shift, cultural copy fixes, LICENSE added. Open: zip and fuses (Phase 6), Quit from pause, Tagalog glossary text, live evals and playtests |
| Tests | 1232 backend passing from the repo root or `backend`, 94% coverage, E7 50 of 50 (rerun 2026-11-03). ruff, mypy --strict, typecheck, lint, prettier clean. npm audit: 32 moderate, all in dev tooling (eslint, electron-builder chains) |
| CI, git hooks | `.github/workflows/ci.yml` (Windows, Python 3.13, Node 22). First run after EHIBE pushes. No git hooks |

## Pending queue

Ordered. Canonical: `docs/FINALIZATION_PLAN.md`. Phases 1, 2 and 4 done.

1. Manual: EHIBE. Phase 3: claim credits, confirm Contributor mode off, fill `docs/rules-notes.md`, paste the key in KeySetup and `backend/.env`, then say "key is in"
2. Claude with EHIBE watching. Phase 3 smoke scripts and `python -m smoke.assets --date 2026-11-03` inside the $15 day budget. EHIBE rates 20 sprites for E5
3. Claude. Phase 5 FIL and ENG screenshots of every screen, overflow fixes, impeccable audit of the Night HUD
4. Manual: EHIBE. Freeze at Nov 3 6:00 PM SGT: `git tag freeze-nov3` and push
5. Claude. Phase 6 packaged zip with the backend bundled and fuses on (ADR-0111)
6. Manual: EHIBE with Claude. Phase 7 ffmpeg (`winget install Gyan.FFmpeg`), Playtest 1 Demo Safe with Wi-Fi off, table run with push and steal, two consented nights, evals E1 to E6, replay check
7. EHIBE with Claude. Phase 8 video, LICENSE, README numbers, submission text, secret scan, push and submit by Nov 4 11:00 PM SGT

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

Each has an ADR in `docs/decisions/`.

B1 to B11 closed (ADR-0101 to ADR-0110, B11 in M3). B12 planned through electron-builder `electronFuses` in Phase 6 (ADR-0111, no new dependency). B13 done 2026-11-03, `@electron-toolkit/preload` removed. B15 approved and closed 2026-11-03 (schema v2 stays).

| ID | Open issue | Owner |
|---|---|---|
| B12 | Fuses not applied yet. Lands with the packaged zip | Claude, Phase 6 |
| B14 | ffmpeg not on PATH. Venv uses Python 3.13 per ADR-0101 | Manual: EHIBE (D14) |

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
| Run backend | `cd backend`, set `DESKTOP_TOKEN` (64 hex) and `DESKTOP_DEV=1`, then `.venv\Scripts\python -m uvicorn server:create_app_from_env --factory --host 127.0.0.1 --port 8765`. Full steps: `docs/engineering/troubleshooting.md` |
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
| Finalization roadmap, Nov 3 to Nov 5 | `docs/FINALIZATION_PLAN.md` |
| Working prompt | `docs/prompts/FEATURE_PROMPT.md` |
| Schedule, risks, demo | `docs/delivery/` |
| Release zip, live API, judging score | `docs/delivery/release-and-packaging.md`, `docs/delivery/live-api-runbook.md`, `docs/delivery/judging-scorecard.md` |
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

Accepted: ADR-0001 to ADR-0012 and ADR-0101 to ADR-0112. ADR-0111 covers the packaged zip and origin. ADR-0112 covers the finalization scope. ADR-0012 holds the MVP build defaults (damage with shields, walls, ties, fail-closed token). Proposed: none. Index: `docs/decisions/README.md`.
