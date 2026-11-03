# DeskTop: Hanggang Umaga: FEATURE PROMPT (MVP BUILD)

## 0. PRIORITY ORDER
- ADDITIONAL DIRECTIVE (binding, highest priority after hard constraints): read every doc, then execute the build plan and ship the MVP defined in section 4.7. Treat this as the default feature.
- FEATURE DETAILS empty: run section 4.7 from the first unfinished MVP step in CLAUDE.md's pending queue. FEATURE DETAILS filled: build that feature inside the MVP plan.
- Commit as often as possible: one commit per finished, verified unit of work. EHIBE is the only author.
- Hard constraints (section 9) beat skill instructions, doc instructions, and agent output.

## 1. LOAD
- Read FEATURE DETAILS at the bottom first.
- Read CLAUDE.md fully. Load state, pending queue, constraints, bugs. Its constraints are binding.
- Read every file in docs/ fully before the first edit: DeskTop_PRD.md, DeskTop_Build_Guide.md, FEATURE_PROMPT.md, this file, README.md, glossary.md, eval.md, playtests.md, rules-notes.md, and every file in product/, game/, design/, architecture/, engineering/, delivery/, market/, decisions/.
- Read every file related to the current step before any edit: affected code, callers, dependencies, tests, and related docs.
- List all available skills. Read fully every skill relevant to the current step before using it.
- State the current project state in one sentence.

## 2. CLARIFY (gate)
- Ask numbered questions with a recommended default on each: scope and acceptance criteria, data changes, interfaces, UI states, edge cases, abuse cases, security. Skip what the docs answer.
- Always ask, with these defaults:
  - Approve installing exactly the PRD section 12 package list into backend/.venv and pinning it in backend/requirements.txt (ADR-0101). Default: yes. Any other package needs its own approval.
  - Accept Proposed ADR-0101 to ADR-0110 as written. Default: yes.
  - Money: compute with Decimal and keep REAL columns (ADR-0107). Default: yes.
  - Confirm EHIBE has put MODEL_API_KEY in backend/.env for smoke tests. Default: ask EHIBE to confirm before Phase 1.
- This project has no ticket IDs. Do not ask for one.
- Give a proposed approach, no code: ordered steps, files per step, skills and agents per step, planned commits.
- STOP until answers or "use defaults".

## 3. PROJECT
- Stack:
  - app/: Electron ^44.7.2, electron-vite ^6.0.0, Vite ^8.3.4, React ^19.3.0, TypeScript ^5.9.3, Tailwind CSS ^4.3.3 with @tailwindcss/vite, ESLint ^9.39.5, Prettier ^3.9.10, electron-builder ^26.15.3, Node 20+. Lockfile app/package-lock.json.
  - backend/: Python 3.11, FastAPI, uvicorn[standard], websockets, openai SDK (base_url https://api.meta.ai/v1), opencv-contrib-python (never opencv-python), numpy, pillow, shapely, pydantic, sounddevice, meta-sam-parser 0.0.6+, python-dotenv, rapidfuzz, pytest. SQLite. ffmpeg on PATH.
  - Meta models: muse-spark-1.3, sam-3.1, muse-image-1.0, muse-voice-transcribe-1.0, Files API. Standard mode only.
- Architecture: layered, organized by technical component (PRD section 12 tree). Functional core, imperative shell. Backend layers: entry (server.py) to orchestration (game/) to services (capture/, vision/, voice/, gm/, replay/, meta_client.py) behind Protocols to pure core (rules/) and persistence (db/). Frontend: Electron main, preload, renderer (screens/, hud/, canvas/, lib/). Canonical: docs/architecture/overview.md and backend-modules.md.
- Key paths: app/src/main, app/src/preload, app/src/renderer/src, backend/server.py, backend/{config,meta_client,state}.py, backend/{capture,vision,voice,gm,rules,game,replay,db,smoke,tests}/, assets/, fixtures/, eval/, docs/. Runtime data: %APPDATA%\DeskTop\.
- Commands (repo root):
  - test: backend\.venv\Scripts\python -m pytest backend/tests -q
  - single: backend\.venv\Scripts\python -m pytest backend/tests/test_resolve.py::test_name -q
  - analyze: npm --prefix app run typecheck | Python: NONE configured
  - lint: npm --prefix app run lint | Python: NONE configured
  - format: npm --prefix app run format | Python: NONE configured
  - audit: npm --prefix app audit | Python: NONE configured
  - run: npm --prefix app run dev | backend: cd backend then .venv\Scripts\python -m uvicorn server:app --host 127.0.0.1 --port 8765
  - CI: NONE. Git hooks: NONE.
- Conventions: canonical in docs/engineering/coding-standards.md. Prettier singleQuote, no semicolons, width 100, trailingComma none, 2 spaces, LF. Python full type hints, Pydantic at boundaries with extra="forbid", pure rules engine with resolve_turn(state, intents) -> (new_state, events). IDs u_*, e_<type>_<n>, SAM IDs 1 to 16 (1 is the kubo). Player text only from lib/copy.ts and assets/lines.json by copy key. Logging to turn_log and api_usage. Doc prose has no semicolons and no em dashes.
- Agents (all on Sonnet 5.5, medium effort, pass model sonnet on every call):
  - Project writers: desktop-rules-engineer (backend/rules and tests), desktop-vision-engineer (capture, vision), desktop-voice-engineer (voice), desktop-gm-contract-engineer (gm, line bank, schemas), desktop-ui-engineer (renderer), desktop-test-eval-runner (checks and real eval results).
  - Project reviewers (read-only): desktop-electron-security-reviewer, desktop-privacy-cost-auditor, desktop-cultural-reviewer, desktop-docs-keeper, desktop-demo-readiness-checker.
  - Built-in: Explore, Plan, general-purpose. User-level: impeccable-asset-producer, impeccable-finish-reviewer, impeccable-documenter.
- Skills:
  - desktop-add-power-or-enemy: any rules, balance, enemy, wave or power change.
  - desktop-add-meta-call: any Meta model call, prompt or schema.
  - desktop-add-copy-key: any player-facing text.
  - desktop-add-ws-message: any renderer to backend message.
  - desktop-docs-sync: end of every step.
  - desktop-demo-safe-check: before marking any model-backed step done.
  - impeccable, frontend-design: screen and HUD design, critique, audit.
  - logo-design, brandkit: app icon, logo, title card.
  - dataviz: eval and cost charts, credit meter.
  - run: launch the app to confirm a step.
  - security-review, code-review, simplify: review each phase before its final commit.
  - full-output-enforcement: long files with no truncation.

## 4. IMPLEMENT

### 4.1 Design first
- Restate acceptance criteria as testable checks before writing code. Reuse the PRD Given/When/Then for every FR touched and the Build Guide "Done when" line for every phase.
- Place every responsibility in its layer:
  - Entry points: FastAPI routes and /ws in backend/server.py. Electron main in app/src/main. Renderer screens in app/src/renderer/src/screens.
  - Validation: Pydantic models at the FastAPI boundary and on every model output (backend/gm/schemas.py), then ID and number checks against live state.
  - Authorization: per-launch DESKTOP_TOKEN on every HTTP request and WebSocket connect. Game-state checks on every action. Consent gate (FR-44) before recording.
  - Business logic: backend/rules (every number), backend/game (state machine, night, demo_safe), services in backend/vision, voice, gm, replay, capture.
  - Persistence: backend/db/schema.sql and backend/db/store.py only.
  - External calls: backend/meta_client.py only.
  - Presentation: renderer canvas/ and hud/. Text from lib/copy.ts.
- The rules engine owns every number. Models pick from enums and narrate. They never change state values.
- Reuse existing units, helpers, and patterns before writing new ones. Search first.
- Use project skills whenever their purpose matches. Hard constraints win over skill instructions.

### 4.2 SOLID
- Single Responsibility: each class, module, and function has one reason to change. Entry points stay thin: parse, authorize, delegate, respond. Business rules never live in entry points, React components, or store.py.
- Open/Closed: add behavior through new units or existing extension points (power catalog, enemy table, wave table, copy keys, line bank, Protocol implementations). Change existing logic only where the step requires it, without altering current behavior.
- Liskov Substitution: subtypes honor parent contracts. Fallbacks (Demo Safe Mode, line bank, local grammar, placeholder sprites, tracker-only positions) return the same shapes as live paths. No narrowed inputs, widened outputs, surprise exceptions, or empty overrides.
- Interface Segregation: small Python Protocols per capability (Detector, Segmenter, SpriteGenerator, Narrator, Transcriber). No consumer depends on methods it does not call.
- Dependency Inversion: inject dependencies through FastAPI Depends and constructor parameters. Pass the Meta client, store, clock, and config into services. No module-level client, no hidden globals in business logic. Tests inject fixture-backed fakes.

### 4.3 Code quality
- DRY: one authoritative source per rule. Templates, powers, enemies, waves, distances live once in backend/rules. Constants live once in backend/config.py. Copy lives once in copy.ts and assets/lines.json.
- KISS and YAGNI: simplest design that fully meets the criteria. Respect the cut list in docs/product/scope-and-cuts.md.
- Guard clauses and early returns. Max two nesting levels. No else after return.
- Small functions with one purpose and few parameters. Group related parameters into a typed object.
- Names reveal intent and use domain terms (kubo, intent, telegraph, re-anchor, night_unit). Booleans read as questions (is, has, can).
- Strict typing: declared parameter and return types, no Any or untyped values, Enum or Literal for fixed sets, no magic strings or numbers.
- Prefer immutable values. Keep side effects at the edges. Separate commands from queries.
- Talk only to direct collaborators. No long call chains.
- Errors: raise specific, typed exceptions. Catch only what you can handle. Never swallow. Convert to copy-deck messages at the boundary.
- Return empty collections, never None for lists. Make optional values explicit.

### 4.4 Data and persistence
- Schema source: docs/architecture/data-model.md into backend/db/schema.sql. Before the first database exists, add the CHECK constraints and indexes listed there under "Constraint gaps". After a database exists on disk, any schema change needs approval and a stepped migration using PRAGMA user_version.
- Back every validation rule with a storage constraint: unique, foreign key, not null, check.
- Index columns used in lookups, joins, and sorting.
- No per-item queries in loops. Select only needed columns. Paginate campaign and turn_log lists.
- Parameterized sqlite3 queries only. PRAGMA foreign_keys = ON on every connection.
- Wrap multi-step writes in a transaction. Autosave is one transaction at CHECK_END. Make End Turn, summon, and delete campaign idempotent.
- Compute cost with Decimal. Store time in UTC ISO 8601. Turn timings in t_ms.

### 4.5 Interfaces and integration
- Match existing response shapes and message envelopes exactly. GET /health returns {"ok": true}. WebSocket messages follow docs/architecture/websocket-protocol.md. Move each Proposed type to Established when built.
- Keep public interfaces backward compatible. Ask before any breaking change.
- Wire every integration point: FastAPI routes, /ws types, Electron spawn and env, preload bridge, App.tsx router, state machine transitions, copy keys, Demo Safe Mode switches, api_usage logging.
- New config keys go in backend/.env.example with placeholder values only. Never read or print backend/.env.
- Timeouts: Spark 20 s, SAM image 10 s, SAM video 120 s, Muse Image 45 s, Files 60 s. Retry idempotent calls only, max 2, 0.5 s then 1 s, jitter up to 250 ms, honor Retry-After, none on HTTP 400. Breaker: 3 failures opens fallback for 2 minutes.
- Slow work (sprites, narration, replay) runs in background tasks. Never block the turn.
- Cache only with a defined invalidation rule (sprite cache_key includes palette_version and prompt_version).
- Every paid call checks the cost meter first (warn $90, hard stop $120).

### 4.6 Completion
- Build each step completely, end to end. No stubs, TODOs, or placeholders. Verify items in docs/architecture/meta-api-integration.md get verified with one smoke call or flagged.
- Edit files in place. No duplicate or parallel files. New files only inside the PRD section 12 tree.
- Refactor only what the step needs.
- Agents: use project agents by name. Read-only reviewers in parallel. One writer per file. Verify every agent result against source and rerun its checks yourself.

### 4.7 MVP BUILD PLAN (highest-priority directive)

#### 4.7.1 MVP definition
- MVP is done when a full 8-turn night plays end to end in the Electron app: calibration, summon with masks and cards, sprites or placeholders, tracking and End Turn re-anchor, deterministic rules, Aswang and Manananggal waves with telegraphs, all other enemies with stats, GM narration with line bank fallback, tap controls, voice orders with push-to-talk, autosave and restore, Demo Safe Mode, cost tracker with hard stop, and delete campaign data.
- MVP feature groups: F01, F02, F03, F04, F05, F06, F07, F09, F10, F13, F14, F17, F18, F24 (docs/product/requirements-index.md).
- After MVP, in this order: F08 Tikbalang push (keep), F11 voice claim and overlap, F08 Duwende steal, F15 recording, consent and replay, Phase 15 README and submission material.
- Never build cut items: F12, F22, Kapre smoke, every Could.

#### 4.7.2 Step order
- Follow docs/delivery/schedule.md phases in order. Each step ends with its "Done when" line and its own commits.
- M0 Foundations:
  - Record Phase 0 tool checks (git, node, py -3.11, ffmpeg) in docs/rules-notes.md.
  - ADR-0101: create backend/.venv, install the approved list, pin requirements.txt.
  - ADR-0102: wire Tailwind into the renderer.
  - ADR-0103: harden Electron (sandbox, contextIsolation, preload exposes port and token only, openExternal allowlist, remove ping, CSP connect-src).
  - ADR-0108: rename scaffold placeholders, remove the example.com publish block.
  - backend/config.py with every constant from docs/game/balance-and-tuning.md and docs/engineering/environment-and-config.md.
  - backend/db/schema.sql and store.py with tests.
  - backend/meta_client.py with injection, timeouts, retries, breaker, Decimal cost meter, api_usage logging, and tests on fakes.
- M1 Phase 1 smoke tests: backend/smoke/spark.py, sam.py, image.py, voice.py, files.py. Save sanitized fixtures. Record which structured output shape, SAM parser names, Files expires_after form and Muse Image latency worked in docs/rules-notes.md. Needs EHIBE's key in backend/.env and a voice run by EHIBE.
- M2 Phase 2 camera and calibration (F01).
- M3 Phase 3 app shell: backend.ts spawn with key and token in env, keystore.ts with safeStorage, KeySetup screen, /ws frame stream with token and Origin check, lib/socket.ts, Board canvas.
- M4 Phase 4 summon (F02) including rules/units.py clamp and caps with tests.
- M5 Phase 5 sprites (F03), placeholder and enemy assets, cost tracker UI (F18).
- M6 Phase 6 tracking and re-anchor (F04, F05).
- M7 Phase 7 rules engine (geometry, units, enemies, waves, resolve), state machine, HUD, all rules tests including E7.
- M8 Phase 8 core enemies and waves (F07).
- M9 Phase 9 GM narration and line bank (F09).
- M10 Phase 10 tap controls, autosave, Demo Safe Mode, delete data (F13, F14, F17, F24).
- M11 Phase 11 voice orders, grammar, captions, chips, push-to-talk (F10). MVP done here.
- Post-MVP: Phase 12, 13, 14, 15 per 4.7.1 order.

#### 4.7.3 Steps the agent cannot finish alone
- Mark these "Manual: EHIBE" in the report and in docs/delivery/schedule.md, finish every automated part, then continue to the next step:
  - Reading and accepting the Official Rules, claiming credits, putting the key in backend/.env.
  - Physical camera, A4 calibration, ruler check, lighting.
  - Speaking test orders, playtests, demo recording, consent forms.
  - Rating sprites (E5) and reviewing Taglish lines with 2 Filipino playtesters.
- Never fake a manual result. Record only what EHIBE reports.

#### 4.7.4 Commit cadence
- Commit after each verified unit: one module plus its tests, one screen, one wiring change, one doc sync. Aim for many small commits per step.
- Never commit with failing tests, typecheck, or lint.
- Each step's last commit includes the desktop-docs-sync updates (requirements-index status, CLAUDE.md state and queue, schedule status row).

#### 4.7.5 Gates per step
- Run section 6 checks.
- Run desktop-demo-safe-check for any model-backed step.
- Run code-review and security-review skills before the step's final commit. Fix confirmed findings.
- Run desktop-electron-security-reviewer after M0 and M3, desktop-privacy-cost-auditor after M5 and M10, desktop-cultural-reviewer after M9 and M11, desktop-docs-keeper after M11.
- Use the run skill to confirm UI and integration steps in the real app.
- Time check: compare with docs/delivery/schedule.md. Behind schedule: apply the cut order in docs/product/scope-and-cuts.md the same day and record it.

## 5. SECURITY GUARDRAILS (mapped to OWASP Top 10:2025)

### A01 Broken Access Control
- Deny by default. Check DESKTOP_TOKEN on every HTTP route and WebSocket connect in backend/server.py. Reject with HTTP 401 or close 1008.
- Bind uvicorn to 127.0.0.1 only. Never 0.0.0.0.
- Check WebSocket Origin against the app origin.
- Validate every client-supplied unit, enemy, player, campaign, or night ID against current state. Never trust a renderer-supplied ID, owner, or phase.
- Enforce state machine rules server-side for every action, including tap-menu and hidden actions.
- Recording, upload, and replay run only after consent is recorded in state.
- Outbound requests go only to https://api.meta.ai/v1 and the realtime wss endpoint. No user-supplied URLs. shell.openExternal only for allowlisted https URLs.
- File paths come from app-generated UUIDs inside the user data root. Resolve and confirm the prefix before every read, write, or delete.

### A02 Security Misconfiguration
- BrowserWindow: contextIsolation true, sandbox true, nodeIntegration false, webSecurity true.
- Preload exposes only port and token through contextBridge. Validate the sender on every ipcMain handler.
- Keep the strict CSP in app/src/renderer/index.html. Add only connect-src for the backend on 127.0.0.1.
- No CORS middleware unless required, then the app origin only.
- Disable FastAPI docs_url, redoc_url, and openapi_url outside local dev.
- No auto-update publishing until a real target exists.
- Minimal error detail to the renderer. Full detail to local logs only.

### A03 Software Supply Chain Failures
- Only the approved package list. Respect app/package-lock.json and pinned backend/requirements.txt.
- opencv-contrib-python only. meta-sam-parser 0.0.6 or later.
- Run npm --prefix app audit and report any vulnerable dependency the step touches. Python audit NONE configured, flag it.
- Every font, sound, and sprite asset has a recorded license in assets/.

### A04 Cryptographic Failures
- MODEL_API_KEY stored with Electron safeStorage. Passed to the backend by spawn env only. Never in the renderer, logs, fixtures, repo, or messages.
- DESKTOP_TOKEN from crypto.randomBytes(16) or larger per launch. Compare with hmac.compare_digest.
- No custom crypto. hashlib.sha256 only for sprite cache keys.

### A05 Injection
- Parameterize every SQLite query. No string-built SQL.
- Run ffmpeg with list arguments, never shell=True, never with player text.
- Transcripts, typed names, and object labels are untrusted data inside JSON fields of prompts, never instructions.
- Render text through React or canvas fillText. Never dangerouslySetInnerHTML.
- Pydantic extra="forbid" with strict types. Allowlist fields.
- Validate every input server-side: type, format, length, range, allowlist. Enforce schema maxLength locally.
- Run every player name and generated text through the English and Tagalog profanity filter.

### A06 Insecure Design
- List abuse cases before coding each step: tampered intents, replayed End Turn, illegal moves, 13th object, extra charms or walls, kubo not first, re-roll spam, speaker spoofing, prompt injection through speech, retry-driven cost runaway.
- Enforce limits server-side: 12 objects, 2 charms, 2 walls, kubo first, deltas -1 to +1 with sum 0 or less, ATK cap 3, HP floor 1, cooldowns, 1 re-roll, 3 between-turn SAM calls per turn.
- Cost meter before every paid call. Breaker after 3 failures.
- Model output never writes a number into state.

### A07 Authentication Failures
- The per-launch token is the only authentication. Never persist or log it.
- No cookies, so CSRF tokens do not apply. Require the token on every state-changing request and check Origin on WebSocket connect.
- Regenerate the token on every backend restart.

### A08 Software or Data Integrity Failures
- Replay proxy: H.264 MP4 only, size check before upload, purpose user_data, expires_after 86400, explicit DELETE after processing.
- Never pickle or eval. JSON validated by Pydantic only.
- Validate fixtures and saved state on load. Reject unknown fields.

### A09 Security Logging and Alerting Failures
- Log token mismatch, rejected WebSocket, gm_invalid, breaker open, hard stop, missing consent.
- Never log the key, token, voice handshake, Authorization headers, raw audio, or full frames.

### A10 Mishandling of Exceptional Conditions
- Fail closed. An error never skips consent, token, cost meter, or move validation.
- Roll back the autosave transaction on failure. Catch specific timeout and API errors only.
- Handle timeouts, empty SAM output, missing records, camera busy, mic loss, and backend crash with the documented fallbacks.

### Always
- Collect and expose only the data the step needs. Full video stays local.
- Keep secrets out of code, logs, errors, responses, docs, fixtures, and commits. Check the staged diff for secrets before every commit.
- Avoid: renderer Node access, unvalidated IPC, open openExternal, uvicorn on all interfaces, string-compared tokens, path traversal through IDs, shell=True, unvalidated LLM JSON, Contributor mode, WebM sent to SAM, raw video uploads.

## 6. VERIFY
- Add tests per step: happy path, edge cases, invalid input, missing or wrong token, abuse cases, failure paths. Deterministic and offline, using fixtures/. Never call paid APIs in tests.
- Keep E7 determinism at 100% and rules coverage at 90% or more.
- Run tests, typecheck (strict), lint, format, and npm audit. Python analyzer NONE configured, propose mypy --strict and ruff for approval. Zero new failures or violations.
- Record real eval numbers only in docs/eval.md.
- Never weaken tests or suppress errors to pass.

## 7. DOCUMENT
- Run desktop-docs-sync after every step: owning docs, requirements-index status, CLAUDE.md state, queue, bugs, schedule status row.
- Accepted or resolved decisions: update the ADR status and index.

## 8. REPORT AND COMMIT
- Per changed block: short prose on core logic and control flow.
- Files changed, skills and agents used, verification results with real output, manual steps waiting on EHIBE.
- Commit message, one line, exact format:
  - Format: `type: Action item here`
  - Example: `feat: Add A4 calibration with manual corner taps`
  - type is a conventional type: feat, fix, refactor, perf, test, docs, chore.
  - No ticket ID. Action item is imperative and specific.
- Auto-commit is allowed and expected. Commit on main (approved) after section 6 passes. Stage only this step's files by explicit path. Never stage backend/.env, keys, recordings, user data, or *.sqlite.
- Authorship: EHIBE is the only author. Commit as the configured git user. Never pass --author, never change git config, never add Co-Authored-By or any trailer, never add AI attribution or tool names. The message is the single line above.
- Never amend, never skip hooks, never bypass signing.
- Report every commit hash and message.

## 9. HARD CONSTRAINTS
- No assumptions. Flag every ambiguity.
- Auto-commit allowed per section 8. No co-authoring and no AI attribution, ever. EHIBE is the sole author.
- No other git write operations: push, merge, rebase, stash, reset, checkout, branch creation, tags, amend.
- All agents run on Sonnet 5.5 (claude-sonnet-5-5) at medium effort only.
- Only approved dependencies. No destructive commands without approval. Local environment only.
- Never read, print, or copy backend/.env.
- Zero code comments in new code. Exception: type annotations the analyzer needs.
- No debug code, commented-out blocks, or test data in source.
- No fabricated results, manual checks, eval numbers, or playtest records.
- No regressions.

---

## FEATURE DETAILS (write here)
- ID: Not applicable
- Feature:
