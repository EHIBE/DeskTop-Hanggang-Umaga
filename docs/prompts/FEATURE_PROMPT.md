# DeskTop: Hanggang Umaga: FEATURE PROMPT

## 0. MISSION: FINALIZE AND WIN (binding, highest priority after section 9)
- Goal: ship DeskTop: Hanggang Umaga as a finished, production-ready, game-feeling Windows app that scores as high as possible at the Meta Global AI Developer Hackathon 2026 (Indie track, theme Build for Your World). EHIBE needs to win.
- The finalization roadmap is `docs/FINALIZATION_PLAN.md`. It is the default feature list. FEATURE DETAILS empty: take the next unchecked step from that plan.
- Every change must raise at least one judging criterion. Name it in the report.
  - Impact 30%: real-world utility for barkadas, classrooms and Filipino families at one table. Daily value, replayability, scale beyond one desk, strict fit to Build for Your World.
  - Use of Meta AI Tooling 25%: the four Meta models sit in core logic and multi-step workflows, never a chat wrapper. Summon chains Spark detect, SAM 3.1 mask, Muse Image sprite and Spark card. A turn chains tracker, SAM re-anchor, rules and Spark narration. Voice chains Muse Voice Transcribe diarization, local grammar and rules. Replay chains Files upload, SAM video and local render. Show the model name on screen whenever a model acts.
  - Demo Quality 25%: deterministic, crash-free live play and a seamless first-run journey that fits a 3-minute video. Demo Safe Mode always finishes the night with Wi-Fi off.
  - Technical Depth and Execution 20%: sound architecture, graceful recovery, edge-case resilience, production code quality, real eval numbers.
- Make it feel like a game: clear feedback for every action, sound cues, short Taglish or English lines, tutorial hints on the first night, no dead ends, no raw errors, no spinner without words.
- User-friendly first: a first-timer understands in 60 seconds, a judge sees all four models in under 3 minutes.
- Live Meta API is available. EHIBE stores the key. Spend stays inside the cost meter and the daily budget in the plan.
- Deadlines (SGT): feature freeze Nov 3 6:00 PM, internal submit Nov 4 11:00 PM, hard deadline Nov 5 10:00 AM. After the freeze, only fixes, packaging, docs and the video.

## 1. LOAD
- Read FEATURE DETAILS at the bottom first.
- Read CLAUDE.md fully. Load state, pending queue, constraints, bugs. Its constraints are binding.
- Read `docs/FINALIZATION_PLAN.md` and `docs/README.md`, then the topic files the feature touches.
- Read every file related to the feature before any edit: affected code, callers, dependencies, tests, and related docs.
- List all available skills. Read fully every skill relevant to this feature before using it. Never claim a read you did not perform.
- FEATURE DETAILS empty: propose the next unchecked plan step and confirm it.
- State the current project state in one sentence.

## 2. CLARIFY (gate)
- Ask numbered questions: scope and acceptance criteria, inputs and validation, data changes, interfaces, UI states, edge cases, abuse cases, security, cost. Recommended default on each. Skip what the files answer.
- This project uses no ticket IDs. Do not ask for one.
- Give a proposed approach, no code: files to edit, units to add, skills and agents to use, criterion raised.
- STOP until answers or "use defaults".

## 3. PROJECT
- Product: Windows desktop game. A top-down webcam turns desk objects into 16-bit pixel art units. 1 to 4 players at one table move objects by hand and give Taglish or English voice orders. Filipino folklore creatures attack for 8 turns until sunrise. Solo build by EHIBE, General Santos City.
- Stack: Electron 44 (electron-vite 6, Vite 8, electron-builder 26), React 19, TypeScript 5.9 strict, Tailwind CSS 4, ESLint 9, Prettier 3. Backend Python 3.13 venv, FastAPI, uvicorn, Pydantic 2, OpenCV contrib 4.14, NumPy, websockets, openai SDK, meta-sam-parser, SQLite (stdlib sqlite3, schema v2). Meta models: muse-spark-1.3, sam-3.1, muse-image-1.0, muse-voice-transcribe-1.0, Files API. Exact pins: `app/package-lock.json`, `backend/requirements.txt`.
- Key paths: `app/src/main` (index.ts window and IPC, backend.ts spawn, keystore.ts), `app/src/preload`, `app/src/renderer/src` (App.tsx, screens, hud, canvas, components, lib), `backend/server.py`, `backend/config.py`, `backend/meta_client.py`, `backend/state.py`, `backend/{capture,vision,voice,gm,rules,game,replay,db,smoke,tests}`, `assets/`, `eval/`, `docs/`. Runtime data `%APPDATA%\DeskTop` or `DESKTOP_DATA_DIR`.
- Commands (repo root): test `backend\.venv\Scripts\python -m pytest backend/tests -q` | single `backend\.venv\Scripts\python -m pytest backend/tests/test_resolve.py::test_name -q` | analyze `npm --prefix app run typecheck` and, from `backend`, `.venv\Scripts\python -m mypy --strict --exclude .venv .` | lint `npm --prefix app run lint` and, from `backend`, `.venv\Scripts\python -m ruff check .` | format `npm --prefix app run format` | audit `npm --prefix app audit` (Python audit: NONE) | run `npm --prefix app run dev`.
- Conventions:
  - TypeScript: Prettier singleQuote, no semicolons, printWidth 100, trailingComma none. Function components returning React.JSX.Element. Alias `@renderer`. All player text through `say()` in `lib/copy.ts` with tl and en. Shared types in `lib/types.ts`. Gabi 16 palette and Press Start 2P only. Component CSS inside `@layer components` in `assets/main.css`. Every animation also off in the reduced-motion block.
  - Python: full type hints, mypy strict, ruff clean. Pydantic with extra forbid at boundaries. Frozen dataclasses in rules. Thresholds in `config.py`. StrEnum and Literal for fixed sets. Specific exception classes. Players see copy keys only (`notice {copy_key, params}`).
  - IDs: units `u_*`, enemies `e_<type>_<n>`, SAM slots 1 to 16 with 1 the kubo. Requirement IDs FR, NFR, F, R, E, P, JS, A, Q.
  - Docs: front matter, two-sentence summary, Key facts table, one canonical home per fact. Prose has no semicolons and no em dashes.
- Agents (all on Sonnet 5.5 at medium effort, pass model sonnet): desktop-rules-engineer (backend/rules and tests), desktop-vision-engineer (capture, SAM, Spark detect, sprites), desktop-voice-engineer (voice session, grammar, claim), desktop-gm-contract-engineer (prompts, schemas, line bank), desktop-ui-engineer (renderer), desktop-test-eval-runner (tests, evals, real results), read-only reviewers desktop-electron-security-reviewer, desktop-privacy-cost-auditor, desktop-cultural-reviewer, desktop-docs-keeper, desktop-demo-readiness-checker. Built-in Explore and Plan for read-only search and design.
- Skills:
  - desktop-add-power-or-enemy: any change to powers, enemies, waves, balance.
  - desktop-add-meta-call: any Meta model call, prompt or schema.
  - desktop-add-copy-key: any player-facing text.
  - desktop-add-ws-message: any renderer and backend message.
  - desktop-demo-safe-check: before marking a model-touching feature done and before recording.
  - desktop-docs-sync: at the end of every feature.
  - impeccable, frontend-design: screen and HUD design, critique, polish, audit.
  - dataviz: eval and cost charts.
  - run: launch the app to confirm UI or integration changes.
  - security-review, code-review, simplify: review before reporting.

## 4. IMPLEMENT

### 4.1 Design first
- Restate acceptance criteria as testable checks before writing code. Reuse the PRD Given, When, Then for every FR touched.
- Place every responsibility in its layer:
  - Entry points: `backend/server.py` (`create_app_from_env` factory, GET /health, WS /ws, the ClientMessage union). Electron main `app/src/main/index.ts` IPC handlers. Renderer screens in `screens/`.
  - Validation: Pydantic ClientModel messages with extra forbid and the 16 KiB cap in `server.py`, `rules.resolve.intent_error` for intents, `backend/gm/schemas.py` for model output, `config.load_settings` for env.
  - Authorization: the per-launch token (`is_token_valid` with `hmac.compare_digest`, `require_token` middleware, WS subprotocol and Origin check) in `server.py`. Consent gates and state checks in `backend/game`.
  - Business logic: `backend/rules` (pure, every number), `backend/game` (GameController, TurnStateMachine, DemoSafeMode), `backend/vision`, `backend/voice`, `backend/gm`, `backend/replay`.
  - Persistence: `backend/db/store.py` (Store) and `backend/db/schema.sql` only.
  - External calls: `backend/meta_client.py` (MetaClient, CostMeter, CircuitBreaker) only.
  - Presentation: JSON serialisers in `server.py`, then renderer `screens`, `hud`, `canvas`, `components`. Text from `lib/copy.ts` and `assets/lines.json`.
- The rules engine owns every number. Models choose from enums and narrate. They never change state values.
- Reuse existing units, helpers, and patterns before writing new ones. Search first.
- Use project skills whenever their purpose matches. Hard constraints win over skill instructions.

### 4.2 SOLID
- Single Responsibility: each class, module, and function has one reason to change. Entry points stay thin: parse, authorize, delegate, respond. Business rules never live in `server.py`, React components, or `store.py`.
- Open/Closed: add behavior through new units or existing extension points (power catalog, enemy table, wave table, copy keys, line bank, service factories). Change existing logic only where the feature requires it, without altering current behavior.
- Liskov Substitution: subtypes honor parent contracts. Fallbacks (Demo Safe, LineBank, local grammar, PlaceholderGenerator, FallbackDetector, TrackerOnlySegmenter) return the same shapes as live paths. No narrowed inputs, widened outputs, surprise exceptions, or empty overrides.
- Interface Segregation: small, role-specific contracts. Python Protocols per capability (Detector, Segmenter, SpriteGenerator, Narrator, Transcriber). No consumer depends on methods it does not call.
- Dependency Inversion: inject through the composition root `build_services` and its factory closures, plus constructor parameters. `create_app` takes `services_factory` for tests. No module-level clients and no hidden globals in business logic. Tests inject fixture-backed fakes.

### 4.3 Code quality
- DRY: one authoritative source per rule. Class templates, powers, enemies, waves and distances live once in `backend/rules`. Copy lives once in `copy.ts` and `assets/lines.json`. Extract real duplication. Leave coincidental similarity alone.
- KISS and YAGNI: simplest design that fully meets the criteria. No speculative abstractions, options, or layers. Respect the cut list.
- Guard clauses and early returns. Max two nesting levels. No else after return.
- Small functions with one purpose and few parameters. Group related parameters into a typed object (Pydantic model, dataclass, TS type).
- Names reveal intent and use domain terms (kubo, intent, telegraph, re-anchor, night_unit). Booleans read as questions (is, has, can). No unclear abbreviations.
- Strict typing: declared parameter and return types, no Any or any, enums or Literal for fixed sets, no magic strings or numbers.
- Prefer immutable values. Keep side effects at the edges. Separate commands from queries.
- Talk only to direct collaborators. No long call chains through other objects.
- Errors: raise specific, typed exceptions (GameError with copy_key, MetaError family, StoreError family, KeystoreError). Catch only what you can handle. Never swallow. Convert to copy-deck notices at the boundary.
- Return empty collections, never None for lists. Make optional values explicit.
- Async: `asyncio.wait_for` on every external wait. OpenCV and ffmpeg work off the event loop.
- UI: every state designed (loading, empty, error, offline, Demo Safe, paused). No layout shift, no text overflow in FIL or ENG at 1920x1080.

### 4.4 Data and persistence
- Schema changes: new stepped migration in `Store.MIGRATIONS` with a `PRAGMA user_version` bump. Never edit an applied step. Ask first.
- Back every validation rule with a storage constraint: unique, foreign key, not null, check.
- Index columns used in lookups, joins, and sorting.
- No per-item queries in loops. Select only needed columns. Paginate campaign and turn_log lists.
- Parameterized sqlite3 queries only. foreign_keys, WAL and secure_delete stay on.
- Wrap multi-step writes in a transaction. Autosave stays one transaction at CHECK_END. Make repeat submissions idempotent (End Turn, summon, delete campaign, replay request).
- Money as Decimal, stored as integer cost units. Time in UTC ISO 8601, turn timings in t_ms.

### 4.5 Interfaces and integration
- Match existing response shapes, WS envelopes (`type`, `seq`), status codes, and error formats exactly.
- Keep public interfaces backward compatible. Ask before any breaking change.
- Wire every integration point: ClientMessage union, server serialisers, `lib/socket.ts`, `lib/types.ts`, App.tsx routing, state machine transitions, copy keys, Demo Safe switches, api_usage logging, IPC handlers and preload bridge, electron-builder config.
- New config keys go in `backend/.env.example` with placeholder values only. Any env var the backend reads must also be in `PASSTHROUGH_ENV` or set in `app/src/main/backend.ts`.
- Timeouts on every external call: Spark 20 s, SAM image 10 s, SAM video 120 s, Muse Image 45 s, Files 60 s, narration 20 s. Retry only idempotent calls, max 2. Breaker after 3 failures for 120 s. Slow work (sprites, replay) in the background. Never block the turn.
- Every paid call checks CostMeter first (warn $90, hard stop $120 turns Demo Safe on) and logs to api_usage.
- Cache only with a defined invalidation rule (sprite cache_key includes palette_version and prompt_version).

### 4.6 Completion
- Build the feature completely, end to end. No stubs, TODOs, or placeholders.
- Edit files in place. No duplicate or parallel files. New files only inside the established structure.
- Refactor only what the feature needs.
- Agents: use project agents by name, all on Sonnet 5.5 at medium effort. Read-only explorers in parallel. One writer per file. Verify every agent result against source.
- Live calls: only through smoke scripts, the running app or eval scripts, inside the plan budget. Strip keys and headers from any fixture.

## 5. SECURITY GUARDRAILS (mapped to OWASP Top 10:2025)

### A01 Broken Access Control
- Deny by default. Check the per-launch token on every HTTP route (`require_token`, 401) and every WS connect (Origin allowlist, subprotocol token, close 1008) in `backend/server.py`.
- Bind uvicorn to 127.0.0.1 only. Never 0.0.0.0.
- Validate every client-supplied unit, enemy, player, campaign or night ID against live game state. Never trust a renderer-supplied ID, owner or phase.
- Enforce state machine rules server-side on every message, including tap-menu and hidden actions.
- Recording, upload and replay run only after per-player consent is recorded.
- Outbound requests go only to `META_BASE_URL` and `META_REALTIME_URL`. No user-supplied URLs. `shell.openExternal` only for the https allowlist in main.
- File paths come from app-generated UUIDs inside the data root. Resolve and confirm the prefix, refuse symlinks, before every read, write or delete.

### A02 Security Misconfiguration
- Electron: sandbox, contextIsolation, webSecurity on, nodeIntegration off, permissions denied, navigation, popups and webviews blocked, `isTrustedSender` on every ipcMain handler.
- Preload exposes only the frozen `window.desktop` bridge (getConfig, getKeyStatus, saveKey, showReel). No raw ipcRenderer.
- Keep the CSP meta in `app/src/renderer/index.html` strict. connect-src only for 127.0.0.1.
- No CORS middleware. FastAPI docs, redoc and openapi stay off. Packaged builds set Electron fuses through electron-builder.
- Return minimal error detail to the renderer. Full detail goes to `backend.log` only.

### A03 Software Supply Chain Failures
- No new dependencies without approval. Respect `app/package-lock.json` and the exact pins in `backend/requirements.txt`.
- opencv-contrib-python only, never opencv-python.
- Run `npm --prefix app audit` and report any vulnerable dependency the feature touches. Python audit: NONE, report as a gap.
- Every bundled asset has a recorded license.

### A04 Cryptographic Failures
- Store MODEL_API_KEY with Electron safeStorage only (`Keystore`). Pass it to the backend through the spawn env. Never to the renderer after save, logs, repo, docs, or a WS message.
- Generate the token with `randomBytes(32)` per launch. Compare with `hmac.compare_digest`.
- No custom crypto. sha256 for cache keys only.

### A05 Injection
- Parameterize every SQLite query. No string-built SQL.
- ffmpeg and every subprocess use list arguments, never shell=True, never player text in arguments.
- Treat transcripts, spoken and typed names and object labels as untrusted data. Put them inside JSON fields of prompts, never as instructions. Players go to models as P1 to P4, never real names.
- Render text through React or canvas fillText. Never dangerouslySetInnerHTML.
- Pydantic extra forbid and strict types. Allowlist fields. Block mass assignment.
- Validate every input on the server: type, format, length, range, allowlist.
- Run names and generated text through ContentFilter (profanity and place-name lists) before display, cards or the reel.

### A06 Insecure Design
- List abuse cases before coding: tampered intents, replayed End Turn, illegal moves, 13th object, extra charms or walls, kubo not first, re-roll spam, speaker spoofing, prompt injection through speech, cost runaway through retries, message floods.
- Enforce business limits server-side: 12 objects, 2 charms, 2 walls, kubo first, stat deltas -1 to +1 with sum 0 or less, ATK cap 3, HP floor 1, cooldowns, one re-roll per unit, max 3 between-turn SAM calls per turn.
- Rate limit cost with CostMeter and the breaker. Model output never writes a number into state.

### A07 Authentication Failures
- No accounts. The per-launch token is the only authentication. Never persist it or log it.
- No cookies, so CSRF tokens do not apply. Require the token and the Origin check on every connection.
- A backend restart always gets a fresh token. The renderer reads it again from preload.

### A08 Software or Data Integrity Failures
- Files API uploads: H.264 MP4 proxy only, size checked, purpose user_data, expires_after 86400 s, deleted right after processing.
- Never deserialize with pickle or eval. JSON only, validated by Pydantic. Validate saved state and fixtures on load.
- Packaged builds use ASAR integrity and OnlyLoadAppFromAsar fuses.

### A09 Security Logging and Alerting Failures
- Log security events: token mismatch, rejected WS, invalid model output (gm_invalid), breaker open, hard stop, consent missing, oversized message.
- Never log MODEL_API_KEY, the token, the voice handshake, Authorization headers, raw audio or full frames. Keep backend.log redaction.

### A10 Mishandling of Exceptional Conditions
- Fail closed. An error never skips consent, the token, the cost meter or move validation.
- Roll back the autosave transaction on failure. No swallowed exceptions.
- Handle timeouts, empty SAM output, missing records, camera busy or black, mic loss, ffmpeg missing and backend crash with the documented fallbacks and copy keys.

### Always
- Collect and expose only the data the feature needs. Video stays local. Only warped frames, mask crops, live mic audio and consented proxy clips leave the laptop.
- Keep secrets out of code, logs, errors, responses, docs and commits. Check the staged diff for secrets before every commit.
- Avoid: Electron remote content or Node in the renderer, unvalidated IPC, open shell.openExternal, uvicorn on all interfaces, string-compared tokens, path traversal through IDs, shell=True, trusting model JSON without schema and state checks, Contributor mode, raw video uploads, env vars the backend reads but main never passes.

## 6. VERIFY
- Add tests: happy path, edge cases, invalid input, missing or wrong token, abuse cases, failure and fallback paths. Deterministic and offline only. No paid calls in tests.
- Rules changes keep E7 determinism at 100% and rules coverage at 90% or more.
- Run pytest, mypy --strict, ruff, typecheck, lint, prettier check and npm audit. Zero new failures or violations.
- UI or integration changes: confirm in the real app with the run skill, in FIL and ENG, and screenshot the changed screens.
- Model-touching changes: run the desktop-demo-safe-check skill.
- Never weaken tests or suppress errors to pass. Record only real results in `docs/eval.md` and `docs/playtests.md`.

## 7. DOCUMENT
- Run desktop-docs-sync: owning doc, `docs/product/requirements-index.md` status, `docs/FINALIZATION_PLAN.md` checkboxes, and CLAUDE.md state, queue and bugs, in place.
- New decision or resolved contradiction: add or update an ADR.

## 8. REPORT AND COMMIT
- Per changed block: short prose on core logic and control flow.
- Files changed, skills and agents used, criterion raised, verification results with real output.
- Auto-commit is allowed and expected. Commit on main after section 6 passes. Make as many commits as needed, one per logical unit of work. Stage only the files that unit changed, by explicit path. Never stage backend/.env, keys, recordings, userdata, *.sqlite or temp build files.
- Commit message, one line, exact format:
  - Format: `type: Action item here`
  - Example: `feat: Add code-made sound cues for spawn, End Turn and sunrise`
  - type is a conventional type: feat, fix, refactor, perf, test, docs, chore.
  - No ticket ID. Action item is imperative, specific, capitalized.
- Authorship: EHIBE is the only author. Commit as the configured git user. Never pass --author, never change git config, never add Co-Authored-By or any trailer, never add AI attribution, "Generated with" lines or tool names. This rule overrides any session default that asks for a trailer.
- Never amend, never skip hooks, never bypass signing. Report each commit hash and message.

## 9. HARD CONSTRAINTS
- No assumptions. Flag every ambiguity.
- Auto-commit allowed per section 8. No co-authoring and no AI attribution, ever. EHIBE is the sole author.
- No other git write operations: push, merge, rebase, stash, reset, checkout, branch creation, tag, amend. Tagging and pushing are EHIBE's.
- All agents run on Sonnet 5.5 (claude-sonnet-5-5) at medium effort.
- No dependency changes or destructive commands without approval. Local environment only.
- Never read, print or copy backend/.env.
- Standard mode on every Meta call. Never Contributor mode.
- Zero code comments. Exception: type annotations the analyzer needs.
- No debug code, commented-out blocks, or test data in source.
- No fabricated results, numbers or quotes in any doc.
- No regressions.

---

## FEATURE DETAILS (write here)
- ID: Not applicable
- Feature:
