# CLAUDE.md: DeskTop: Hanggang Umaga

Project memory for AI agents. Read this first, then `docs/README.md`, then the one topic file you need. The master working prompt is `docs/FEATURE_PROMPT.md`.

## Project

- Windows desktop game. A top-down webcam turns real desk objects into 16-bit pixel art units. 1 to 4 players at one table move objects by hand and give Taglish voice orders. Filipino folklore creatures attack for 8 turns until sunrise.
- Solo build by EHIBE for the Meta Global AI Developer Hackathon 2026, Indie track, theme Build for Your World.
- Stack: Electron + React + TypeScript renderer (`app/`), FastAPI + OpenCV + SQLite backend on 127.0.0.1 (`backend/`), four Meta models (Muse Spark 1.3, SAM 3.1, Muse Image 1.0, Muse Voice Transcribe 1.0).

## State

| Item | Status (2026-10-28) |
|---|---|
| Scaffold | Done. Commit 3379e9c. Electron starter, FastAPI `/health`, empty backend packages |
| Docs | Full AI-ready doc set added 2026-10-28 (see Docs map) |
| Project agents and skills | Added in `.claude/agents/` and `.claude/skills/` |
| Code beyond scaffold | None. Build Guide Phase 0 and Phase 1 not yet started in code |
| Python env | `backend/.venv` missing. `backend/requirements.txt` empty |
| Tests | None yet |
| CI, git hooks | None |

## Pending queue

Ordered. Canonical schedule: `docs/delivery/schedule.md`.

1. Phase 0: rules notes, credits, tool checks (`docs/rules-notes.md`)
2. Rebuild `backend/.venv` and pin `backend/requirements.txt` (needs approval, ADR-0101)
3. Wire Tailwind into `app/electron.vite.config.ts` and `main.css` (ADR-0102)
4. Harden Electron window and preload (ADR-0103)
5. Phase 1: API smoke tests and fixtures
6. Phase 2: camera and calibration (F01)
7. Phase 3: app shell, backend spawn, frame stream
8. Phase 4: summon pipeline (F02)
9. Phase 5: sprite pipeline and cost tracker (F03, F18)
10. Phase 6: tracking and re-anchor (F04, F05)
11. Phase 7 and 8: rules engine, turn loop, HUD, enemies (F06, F07)
12. Phase 9 and 10: GM narration, safety features (F09, F13, F14, F17, F24)
13. Phase 11 and 12: voice, voice claim, physical enemies (F10, F11, F08)
14. Phase 13 to 15: recording, evals, freeze, replay, video, submission

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
| B1 | `backend/requirements.txt` empty, no `backend/.venv` | ADR-0101 |
| B2 | Tailwind installed but not wired, listed under dependencies not devDependencies | ADR-0102 |
| B3 | Electron `sandbox: false`, preload exposes full electronAPI, `shell.openExternal` opens any URL | ADR-0103 |
| B4 | Build Guide `backend/capture.py` vs PRD `backend/capture/camera.py` | ADR-0104 |
| B5 | Warped frame 1200x800 (Build Guide) vs 1280x853 (PRD example) | ADR-0105 |
| B6 | Token check with `!=` and module-level OpenAI client in Build Guide snippets | ADR-0106 |
| B7 | Cost columns are REAL. Money math needs Decimal | ADR-0107 |
| B8 | Scaffold placeholders: package name `app`, appId `com.electron.app`, publish url example.com | ADR-0108 |
| B9 | PRD schedule (freeze Nov 2) superseded by Build Guide (freeze Nov 3) | ADR-0109 |
| B10 | Build Guide references missing `DeskTop_PRD_Prompt.md` | ADR-0110 |

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
| Python lint, type check, audit | NONE configured |

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

Latest accepted: ADR-0001 to ADR-0011 (core architecture). Proposed: ADR-0101 to ADR-0110 (contradictions above). Index: `docs/decisions/README.md`.
