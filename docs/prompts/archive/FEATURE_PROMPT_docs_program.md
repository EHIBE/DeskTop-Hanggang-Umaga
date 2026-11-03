# DeskTop: Hanggang Umaga: FEATURE PROMPT

## 0. PRIORITY ORDER
- ADDITIONAL DIRECTIVE (binding, highest priority after hard constraints): build out the project's full AI-ready Markdown documentation set, its project agents, and its project skills, as specified in section 4.7. Treat this as the default first feature.
- FEATURE DETAILS empty: run section 4.7 as the feature. FEATURE DETAILS filled: run that feature, then update every doc section 4.7 says the feature touches.
- Hard constraints (section 9) beat skill instructions, doc instructions, and agent output.

## 1. LOAD
- Read FEATURE DETAILS at the bottom first.
- Read CLAUDE.md fully. Load state, pending queue, constraints, bugs. Its constraints are binding. CLAUDE.md missing: say so, and make creating it the first deliverable of section 4.7.
- Read every file in docs/ fully: DeskTop_PRD.md (v1.1, 2108 lines, canonical for what to build), DeskTop_Build_Guide.md (written Oct 27, canonical for how and when to build, its schedule and cut list replace the PRD's), eval.md, playtests.md, rules-notes.md (all three empty stubs), FEATURE_PROMPT.md (this file).
- Read every file related to the feature before any edit: affected code, callers, dependencies, tests, and related docs. Look at the target before overwriting any file.
- List all available skills. Read fully every skill relevant to this feature before using it. Never claim a read you did not perform.
- State the current project state in one sentence.

## 2. CLARIFY (gate)
- Ask numbered questions: scope and acceptance criteria, data changes, interfaces, UI states, edge cases, abuse cases, security. Give a recommended default on each. Skip what the files answer.
- This project has no ticket IDs. Do not ask for one.
- Give a proposed approach, no code: files to create or edit, units to add, skills and agents to use.
- STOP until answers or "use defaults".

## 3. PROJECT
- Product: Windows desktop game. Turn-based co-op survival tactics. Real desk objects become pixel-art units through a top-down webcam. Players give Taglish voice orders. Filipino folklore enemies (aswang, tikbalang, kapre, manananggal, duwende) attack for 8 turns until sunrise. Solo build by EHIBE for the Meta Global AI Developer Hackathon 2026, Indie track, theme Build for Your World. Judging weights (unverified): Impact 30, Use of Meta AI Tooling 25, Demo 25, Technical Depth 20.
- Deadlines (SGT): feature freeze Nov 3 6:00 PM, internal submit Nov 4 11:00 PM, hard deadline Nov 5 10:00 AM (per Build Guide).
- Stack:
  - app/: Electron ^44.7.2, electron-vite ^6.0.0, Vite ^8.3.4, React ^19.3.0, TypeScript ^5.9.3, Tailwind CSS ^4.3.3 with @tailwindcss/vite, ESLint ^9.39.5 (@electron-toolkit/eslint-config-ts, react, react-hooks, react-refresh), Prettier ^3.9.10, electron-builder ^26.15.3, Node 20+. Lockfile app/package-lock.json.
  - backend/: Python 3.11 (py -3.11), FastAPI, uvicorn[standard], websockets, openai SDK (base_url https://api.meta.ai/v1), opencv-contrib-python (never opencv-python), numpy, pillow, shapely, pydantic, sounddevice, meta-sam-parser 0.0.6+, python-dotenv, rapidfuzz, pytest. SQLite. ffmpeg on PATH.
  - Meta models: muse-spark-1.3 (Responses API), sam-3.1, muse-image-1.0, muse-voice-transcribe-1.0 (wss://api.meta.ai/v1/asr/realtime), Files API. Standard mode only, never Contributor mode.
- Key paths: app/src/main (window, backend spawn, keystore), app/src/preload (bridge), app/src/renderer/src (lib, canvas, hud, screens), backend/server.py, backend/{config,meta_client,state}.py, backend/{capture,vision,voice,gm,rules,game,replay,db,smoke,tests}/, assets/, fixtures/, eval/, docs/. Full planned tree: PRD section 12 "Folder structure". Runtime data: %APPDATA%\DeskTop\ (path passed from Electron main at spawn).
- Commands (run from repo root):
  - test: backend\.venv\Scripts\python -m pytest backend/tests -q
  - single: backend\.venv\Scripts\python -m pytest backend/tests/test_resolve.py::test_name -q
  - analyze: npm --prefix app run typecheck | Python: NONE configured
  - lint: npm --prefix app run lint | Python: NONE configured
  - format: npm --prefix app run format | Python: NONE configured
  - audit: npm --prefix app audit | Python: NONE configured
  - run: npm --prefix app run dev | backend: cd backend then .venv\Scripts\python -m uvicorn server:app --host 127.0.0.1 --port 8765
  - CI: NONE. Git hooks: NONE.
- Known contradictions (verify, then fix or flag):
  - backend/requirements.txt is empty and backend/.venv does not exist, although the PRD setup ran pip freeze. Rebuilding the venv and pinning requirements is a dependency change: ask first.
  - Tailwind is installed but not wired into app/electron.vite.config.ts or main.css (PRD section 12 manual steps 2 and 3 not done). Build Guide says install as -D, package.json has it under dependencies.
  - Electron scaffold uses sandbox: false, exposes the whole electronAPI in preload, and opens any URL with shell.openExternal. NFR-24 and PRD say expose port and token only.
  - Build Guide snippets: backend/capture.py vs PRD backend/capture/camera.py (PRD tree wins, scaffold matches it). Warped frame 1200x800 at 20 px per cm vs PRD example 1280x853. Token check with != instead of a constant-time compare. Module-level OpenAI client instead of an injected one.
  - Build Guide references DeskTop_PRD_Prompt.md, which does not exist.
  - PRD cost columns use REAL. Money rule needs exact decimal math.
  - app/package.json name "app", electron-builder appId com.electron.app, productName app, publish url https://example.com/auto-updates are scaffold placeholders.
  - No CLAUDE.md, no root README.md, no .claude/ folder.
- Conventions:
  - TypeScript: Prettier singleQuote, no semicolons, printWidth 100, trailingComma none, 2-space indent, LF, UTF-8. Function components with explicit return types (React.JSX.Element). Import alias @renderer. All player-facing text lives in app/src/renderer/src/lib/copy.ts under PRD section 11 copy keys, Taglish plus English. Shared types in lib/types.ts.
  - Python: snake_case modules, full type hints, Pydantic models mirroring PRD schemas (gm_turn, unit_card, command_parse, recap) in backend/gm/schemas.py. backend/rules is pure: no I/O, no clock, no randomness. Entry signature resolve_turn(state, intents) -> (new_state, events).
  - IDs: units u_*, enemies e_<type>_<n>, SAM object IDs 1 to 16 (1 is always the kubo, 13 to 16 reserved), requirement IDs FR-xx, NFR-xx, F0x, R0x, E1 to E7, P01 to P12.
  - Responses: GET /health returns {"ok": true}. WebSocket /ws messages are JSON with a "type" field (established: {"type": "frame", "jpg", "poses"}).
  - Logging: game events to turn_log (turn, phase, event_type, payload_json, t_ms). Every paid call to api_usage. Validation failures as event_type gm_invalid.
  - Errors: player sees copy-deck lines only (net.down, restore, cmd.unknown). Retries 2 max, backoff 0.5 s then 1 s, jitter up to 250 ms, honor Retry-After, no retry on HTTP 400. Circuit breaker: 3 failures opens fallback for 2 minutes.
  - Doc prose: no semicolons, no em dashes. Semicolons allowed only inside API syntax in code blocks.
- Agents (every agent runs on Sonnet 5.5 at medium effort, see section 4.6):
  - Built-in: Explore (read-only search), Plan (architecture plans), general-purpose (multi-step research), claude-code-guide (Claude Code questions only).
  - User-level: impeccable-asset-producer (clean raster assets from approved mocks), impeccable-documenter (DESIGN.md from a finished build), impeccable-finish-reviewer (review a finished UI build), impeccable-manual-edit-applier (Impeccable live copy edits only).
  - Project-level: NONE yet. Section 4.7 creates them.
- Skills:
  - impeccable: HUD, screens, design critique, accessibility, DESIGN.md and tokens.
  - frontend-design:frontend-design: distinctive non-templated UI direction for screens.
  - stitch-design-taste: agent-friendly DESIGN.md structure.
  - dataviz: eval charts, cost meter, stat tiles, credit meter.
  - logo-design:logo-design and brandkit: app icon, logo, title card, brand board.
  - anthropic-skills:deep-research: market, competitor, folklore, and judging research with sources.
  - anthropic-skills:skill-creator: author and test project skills.
  - find-skills: discover installable skills for a gap.
  - full-output-enforcement: long documents with no truncation or placeholders.
  - init: bootstrap CLAUDE.md.
  - update-config: hooks and permissions in .claude/settings.json.
  - run: launch the Electron app and backend to confirm a change.
  - security-review, code-review, simplify: review pending changes before reporting.
  - Not applicable: claude-api (project uses Meta API through the OpenAI SDK), landing-page and mobile image skills.

## 4. IMPLEMENT

### 4.1 Design first
- Restate acceptance criteria as testable checks before writing code. Reuse the PRD Given/When/Then for every FR touched.
- Place every responsibility in its layer:
  - Entry points: FastAPI routes and the /ws handler in backend/server.py. Electron main in app/src/main. Renderer screens in app/src/renderer/src/screens.
  - Validation: Pydantic models at the FastAPI boundary and on every model output (backend/gm/schemas.py), then ID and number checks against live state.
  - Authorization: per-launch DESKTOP_TOKEN check on every HTTP request and WebSocket connect in backend/server.py. Consent gates (FR-44) in game state.
  - Business logic: backend/rules (numbers), backend/game (state machine, night, demo_safe), backend/vision, backend/voice, backend/gm, backend/replay.
  - Persistence: backend/db/schema.sql and backend/db/store.py only.
  - External calls: backend/meta_client.py only (retries, breaker, cost meter, timeouts).
  - Presentation: renderer canvas/ and hud/ components. Text from lib/copy.ts.
- The rules engine owns every number. Models pick from enums and narrate. They never change state values.
- Reuse existing units, helpers, and patterns before writing new ones. Search first.
- Use project skills whenever their purpose matches. Hard constraints win over skill instructions.

### 4.2 SOLID
- Single Responsibility: each class, module, and function has one reason to change. Entry points stay thin: parse, authorize, delegate, respond. Business rules never live in entry points, React components, or store.py.
- Open/Closed: add behavior through new units or existing extension points (power catalog, enemy table, wave table, copy keys, line bank). Change existing logic only where the feature requires it, without altering current behavior.
- Liskov Substitution: subtypes honor parent contracts. Fallback implementations (Demo Safe Mode, line bank, local grammar, placeholder sprites) return the same shapes as the live paths. No narrowed inputs, widened outputs, surprise exceptions, or empty overrides.
- Interface Segregation: small, role-specific contracts. Python Protocols per capability (detector, segmenter, sprite generator, narrator, transcriber). No consumer depends on methods it does not call.
- Dependency Inversion: inject dependencies through FastAPI Depends and constructor parameters. Pass the Meta client, store, clock, and config into services. No module-level client and no hidden globals inside business logic. Tests inject fixture-backed fakes.

### 4.3 Code quality
- DRY: one authoritative source per rule. Class templates, powers, enemies, waves, and distances live once in backend/rules. Copy lives once in copy.ts and assets/lines.json. Extract real duplication. Leave coincidental similarity alone.
- KISS and YAGNI: simplest design that fully meets the criteria. No speculative abstractions, options, or layers. Respect the cut list in the Build Guide.
- Guard clauses and early returns. Max two nesting levels. No else after return.
- Small functions with one purpose and few parameters. Group related parameters into a typed object (Pydantic model, dataclass, TS type).
- Names reveal intent and use domain terms (kubo, intent, telegraph, re-anchor, night_unit). Booleans read as questions (is, has, can). No unclear abbreviations.
- Strict typing: declared parameter and return types, no Any or untyped values, Enum or Literal for fixed sets (states, classes, powers, moods, actions), no magic strings or numbers. Thresholds go in backend/config.py.
- Prefer immutable values (frozen dataclasses, readonly TS types). Keep side effects at the edges. Separate commands from queries.
- Talk only to direct collaborators. No long call chains through other objects.
- Errors: raise specific, typed exceptions. Catch only what you can handle. Never swallow. Convert to copy-deck messages at the boundary.
- Return empty collections, never None for lists. Make optional values explicit (Optional, T | None).

### 4.4 Data and persistence
- Schema source of truth: backend/db/schema.sql (PRD section 12). No migration mechanism exists. Any schema change after a database exists on disk: ask first.
- Back every validation rule with a storage constraint: unique, foreign key, not null, check (difficulty, result, sam_object_id 1 to 16, cache_key unique).
- Index columns used in lookups, joins, and sorting.
- No per-item queries in loops. Select only needed columns. Paginate campaign and turn_log lists.
- Parameterized sqlite3 queries only. Enable PRAGMA foreign_keys.
- Wrap multi-step writes in a transaction. Autosave is one transaction at CHECK_END. Make repeat submissions idempotent (End Turn, summon, delete campaign).
- Compute cost with Decimal. Flag that api_usage.cost_usd and night.cost_usd are REAL.
- Store time in UTC ISO 8601. Turn timings in t_ms.

### 4.5 Interfaces and integration
- Match existing response shapes, WebSocket message envelopes, status codes, and error formats exactly.
- Keep public interfaces backward compatible. Ask before any breaking change.
- Wire every integration point: FastAPI routes, /ws message types, Electron main spawn and env, preload bridge, renderer screen router (App.tsx), state machine transitions, copy keys, Demo Safe Mode switches, api_usage logging.
- New config keys go in backend/.env.example with placeholder values only. Never read or print backend/.env.
- Timeouts on every external call: Spark 20 s, SAM image 10 s, SAM video 120 s, Muse Image 45 s, Files upload 60 s. Retry only idempotent calls, max 2. Move slow work (sprites, replay) to background tasks. Never block the turn.
- Voice: PCM 24 kHz mono int16, 80 ms frames, send silence while paused, handle close codes 1008, 1011, 1013.
- Cache only with a defined invalidation rule (sprite cache_key includes palette_version and prompt_version).
- Every paid call checks the cost meter first (warn $90, hard stop $120).

### 4.6 Completion
- Build the feature completely, end to end. No stubs, TODOs, or placeholders. Items marked verify in the Build Guide get verified with one call or flagged.
- Edit files in place. No duplicate or parallel files. New files only inside the established structure.
- Refactor only what the feature needs.
- Agents: use project agents by name. Read-only explorers in parallel. One writer per file. Verify every agent result against source.
- Agent model rule: every agent, built-in, user-level, or project-level, runs on Sonnet 5.5 (claude-sonnet-5-5) at medium effort. Pass model "sonnet" on every Agent call. Project agent files set model: sonnet and effort: medium in front matter. Never spawn an agent on any other model or effort.

### 4.7 DOCUMENTATION, AGENTS AND SKILLS PROGRAM (highest-priority directive)

#### 4.7.1 Goal
- Turn the two long docs (PRD, Build Guide) into a complete, navigable, AI-efficient documentation set that covers the whole scope: product, market, game design, visual design, architecture, AI contracts, engineering, security, delivery, demo, and decisions.
- Any AI agent must find the one file it needs in two hops: CLAUDE.md, then docs/README.md, then the topic file.
- Read every doc in docs/ fully before writing anything. Extract every fact, number, ID, table, decision, risk, and open question. Lose nothing.

#### 4.7.2 Source-of-truth rules
- Each fact has exactly one canonical home. Other files link to it by path and ID, and may restate it only in a short summary row marked "Summary. Canonical: <path>#<anchor>".
- PRD wins on what to build. Build Guide wins on schedule, cut list, and build order. Code wins over both on what exists. Record every conflict in docs/decisions/ as an ADR with status Proposed until EHIBE confirms.
- Never invent facts, statistics, prices, quotes, or market numbers. Every external claim carries a source URL and access date. Unsourced claims are labeled Assumption. Fictional quotes stay labeled fictional.
- Keep the PRD and Build Guide unchanged as historical sources. Add a one-line pointer at their top to docs/README.md only if EHIBE approves.

#### 4.7.3 AI-efficiency format (every Markdown file)
- YAML front matter: title, purpose (one line), read_when (task types), canonical_for (list of topics or IDs), sources (paths or URLs), status (draft, active, superseded), last_verified (YYYY-MM-DD), related (paths).
- First body line: a two-sentence summary. Then a "Key facts" table. Then detail sections.
- One topic per file. Target under 300 lines. Split larger topics.
- Stable H2 headings and stable IDs so links and agents never break.
- Tables for specs, numbers, states, and contracts. Short imperative bullets for rules. No filler, no marketing tone in engineering docs.
- Use the project's existing IDs (FR, NFR, F, R, E, P, copy keys, state names). New IDs: ADR-0001, DOC-*, AG-* only where needed.
- Mermaid for flows and state machines. Plain text tree for folders.
- Prose: no semicolons, no em dashes. Dates with timezone (SGT, UTC).
- Mark every unverified item with "Unverified" and the step that will verify it.

#### 4.7.4 Files to create (propose this tree in the CLARIFY gate, then build all of it)
- CLAUDE.md (root): Project (3 lines), State, Pending queue (ordered, from Build Guide phases), Constraints (hard rules from PRD and this prompt), Bugs and contradictions (from section 3), Commands, Docs map, Agents, Skills, Decisions (latest ADRs). Keep under 200 lines. Use the init skill as a starting point, then rewrite to this outline. Link this prompt at docs/FEATURE_PROMPT.md.
- docs/README.md: doc index, read order per task type (rules work, vision work, voice work, UI work, docs work, demo prep), glossary pointer, conventions for adding docs.
- docs/product/: product-brief.md (one-pager, press release, FAQ summary), goals-and-metrics.md (PG, success, guardrail metrics), personas-and-jobs.md (personas, JS-01 to JS-14), requirements-index.md (traceability matrix: FR and NFR ID, priority, feature group, job story, status Planned, Built, Tested, Cut, owning module, test file), scope-and-cuts.md (in scope, non-goals, Won't, current cut list reconciled across PRD and Build Guide), open-questions.md (A1 to A16, Q1 to Q9 with status).
- docs/market/: market-and-audience.md (Philippines first market, barkada, student orgs and classrooms, families, Filipino diaspora, hardware assumptions), competitive-landscape.md (categories: board and party games, AR tabletop, webcam and phone party games, AI game masters, with sourced examples and how DeskTop differs), positioning-and-messaging.md (tagline, value props per persona, Taglish tone), launch-and-community.md (submission description, viral clip plan, channels, voting rules), judging-strategy.md (rubric weights, scorecard, levers from PRD 20.8, what each demo shot proves). Research with anthropic-skills:deep-research. Cite everything.
- docs/game/: core-loop.md, state-machine.md (states, entry, exit, timeouts, Mermaid), units-and-classes.md (class templates, distances, balance caps, clamp rule with the FR-10 example), powers.md (P01 to P12), enemies.md (roster and AI rules, physical interactions, current cuts), waves-and-difficulty.md, combat-math.md, win-lose-score.md, campaign-progression.md (Could, marked not scheduled), balance-and-tuning.md (tunable thresholds and where they live in config.py).
- docs/design/: DESIGN.md (design system: Gabi 16 palette as named tokens with hex, pixel font rules, integer scaling, spacing scale, HUD layout at 1920x1080, component inventory with every state), screens.md (every PRD screen with purpose, elements, and states: loading, empty, error, offline, Demo Safe Mode, paused), hud-components.md (move ring, phase banner, speaker chip, intent arrow, order chips, unit badge, captions, tap menu), copy-deck.md (all copy keys, Taglish and English, rule that copy.ts is canonical once it exists), art-direction.md (sprite style, sprite pipeline art rules, enemy and tile assets, lighting night and dawn), audio.md (sound list, licenses, TTS off), accessibility.md (16 px minimum, shape plus color, captions always on, tap path for every voice action), cultural-care.md (folklore glossary, no place names, no gore, respect rules, playtester review checklist, profanity filter). Use impeccable and frontend-design for direction and stitch-design-taste for DESIGN.md structure. Derive from the PRD, never invent a new visual direction without approval.
- docs/architecture/: overview.md (components, data flow, key decisions), backend-modules.md (every planned module, its single responsibility, public functions, inputs, outputs, dependencies), frontend-modules.md (main, preload, renderer folders), websocket-protocol.md (every message type both directions, fields, examples, token handshake, mark undefined ones Proposed), data-model.md (SQLite tables, constraints, autosave transaction, runtime data paths, delete-campaign scope), meta-api-integration.md (per-model integration table, exact parameters, limits, verify items, fallbacks), ai-contracts.md (system prompt outline, GM input, all four schemas, validation and repair steps, hallucination controls, LLM versus code decision table), sprite-pipeline.md, tracking-and-reanchor.md (tracker, re-anchor ladder, thresholds to tune), voice-pipeline.md (handshake, events, enrollment, overlap, fallbacks, close codes, local grammar), reliability-and-fallbacks.md (timeouts, retries, breaker, graceful degradation NFR-15, edge cases 1 to 31 with detection and response), cost-and-budget.md (unit prices with verification date, per-call and per-night model, guardrails).
- docs/engineering/: setup-windows.md (real current steps, venv rebuild, Tailwind wiring, run commands, flag current gaps), coding-standards.md (Python and TypeScript rules from section 4 of this prompt), testing-strategy.md (pytest layout, fixtures, offline tests, coverage target 90% for rules, E1 to E7 eval plan, how to record fixtures), security-and-privacy.md (threat model, data inventory of what leaves the laptop, Electron hardening checklist, token model, key storage, retention, consent, section 5 of this prompt as a checklist), environment-and-config.md (env keys, config.py constants), git-and-commits.md (main branch, auto-commit rule, commit format "type: Action item", EHIBE sole author, no co-author or AI attribution), definition-of-done.md.
- docs/delivery/: schedule.md (current Build Guide schedule, phases 0 to 15 with Done when and If stuck), risk-register.md (R01 to R19 with score, mitigation, kill switch, live status column), demo-runbook.md (dry-run checklist, Demo Safe Mode procedure, backup recording, live finals plan), video-script.md (2:30 shot list and what each shot proves), submission-checklist.md, readme-outline.md (for the Phase 15 README).
- docs/decisions/: ADR template plus one ADR per major decision already made (turn-based over real-time, hybrid tracking, deterministic rules engine, SQLite over Glimmer memory, chroma key sprites, local-first no cloud hosting, diarization plus enrollment with fallbacks, backend owns camera and mic, ffmpeg H.264 recording, OpenAI SDK for Meta API, all agents on Sonnet 5.5 medium effort) and one Proposed ADR per contradiction in section 3.
- docs/glossary.md: Filipino terms, game terms, technical terms, and ID prefixes in one table.
- Fill eval.md, playtests.md, and rules-notes.md with templates only (headings, empty tables, how to record). Never fabricate results.

#### 4.7.5 Project agents (.claude/agents/*.md)
- Create one file per agent with front matter: name, description (when to delegate, one sentence), tools (least privilege), model: sonnet, effort: medium. Body: role, inputs, owned paths, read-first docs, rules, output format, and "never" list. Read-only agents get Read, Glob, Grep only.
- Every project agent inherits the commit rule: agents never commit, never add co-author trailers, never add AI attribution. Only the main session commits.
- desktop-rules-engineer: backend/rules and its tests. Pure functions, determinism, coverage.
- desktop-vision-engineer: capture, calibration, tracker, SAM, Spark detection, sprite pipeline.
- desktop-voice-engineer: realtime session, grammar, voice claim, fallbacks.
- desktop-gm-contract-engineer: prompts, schemas, validation and repair, line bank.
- desktop-ui-engineer: renderer screens, HUD, canvas, copy.ts. Uses impeccable.
- desktop-electron-security-reviewer (read-only): main, preload, CSP, IPC, token, key storage.
- desktop-privacy-cost-auditor (read-only): data leaving the laptop, retention, consent, api_usage, hard stop.
- desktop-cultural-reviewer (read-only): Taglish copy, folklore accuracy, cultural-care rules.
- desktop-test-eval-runner: runs tests and evals, writes results to docs/eval.md only from real runs.
- desktop-docs-keeper (read-only auditor): checks docs against code and each other, reports drift, broken links, duplicated facts, stale last_verified.
- desktop-demo-readiness-checker (read-only): runs the dry-run checklist against the repo and reports gaps.

#### 4.7.6 Project skills (.claude/skills/<name>/SKILL.md)
- Author with anthropic-skills:skill-creator. Each skill: name, description that states exactly when it triggers, step list, files it touches, docs it reads, verification commands, and a "done when" check. Any skill that spawns agents uses Sonnet 5.5 at medium effort.
- desktop-add-power-or-enemy: add or change a power, enemy, or wave with rules code, tests, docs/game updates, and line bank entries.
- desktop-add-meta-call: add a model call through meta_client with timeout, retries, breaker, cost logging, schema, fixture, offline test, and fallback.
- desktop-add-copy-key: add Taglish and English copy with cultural-care review and docs/design/copy-deck.md sync.
- desktop-add-ws-message: add a WebSocket message type with Pydantic and TS types, token check, and websocket-protocol.md update.
- desktop-docs-sync: after any change, update the owning doc, requirements-index status, CLAUDE.md state, queue, and bugs.
- desktop-demo-safe-check: verify a feature degrades correctly in Demo Safe Mode and offline.
- Before authoring, run find-skills to check whether an existing skill already covers the need.

#### 4.7.7 Docs verification
- Every number in a new doc matches the PRD or Build Guide exactly. Spot-check each file against its source.
- Every internal link resolves. Every FR and NFR ID appears in requirements-index.md. Every copy key appears once in copy-deck.md.
- No fact is canonical in two places.
- Run desktop-docs-keeper over the finished set and fix every finding.

## 5. SECURITY GUARDRAILS (mapped to OWASP Top 10:2025)

### A01 Broken Access Control
- Deny by default. Check the per-launch DESKTOP_TOKEN on every HTTP route and every WebSocket connect in backend/server.py. Reject with HTTP 401 or WebSocket close 1008.
- Bind FastAPI to 127.0.0.1 only. Never 0.0.0.0.
- Check the WebSocket Origin against the app origin.
- Validate every client-supplied unit, enemy, player, campaign, or night ID against the current game state. Never trust a renderer-supplied ID, owner, or phase.
- Enforce state machine rules server-side: an action valid only in PLAYER_PHASE is rejected in any other state, including tap-menu and hidden actions.
- Recording, upload, and replay run only after consent (FR-44) is recorded in state.
- Outbound requests go only to the fixed base URL https://api.meta.ai/v1 and the realtime wss endpoint. No user-supplied URLs. shell.openExternal only for an allowlist of https URLs.
- File paths for sprites, recordings, and baselines are built from app-generated UUIDs inside the userdata root. Resolve and confirm the prefix before every read, write, or delete.

### A02 Security Misconfiguration
- Electron BrowserWindow: contextIsolation true, sandbox true, nodeIntegration false, webSecurity true. Fix the scaffold's sandbox: false.
- Preload exposes only the backend port and token through contextBridge. No full electronAPI, no raw ipcRenderer. Validate the sender on every ipcMain handler.
- Keep the strict CSP in app/src/renderer/index.html. Add only connect-src for ws://127.0.0.1 and http://127.0.0.1 on the backend port.
- No CORS middleware unless required, then allow only the app origin.
- Disable FastAPI docs_url, redoc_url, and openapi_url outside local dev.
- Disable auto-update publishing (example.com placeholder) until a real target exists.
- Return minimal error detail to the renderer. Full detail goes to logs only.

### A03 Software Supply Chain Failures
- No new dependencies without approval. Respect app/package-lock.json. Pin backend/requirements.txt with exact versions once approved.
- Install opencv-contrib-python only. meta-sam-parser 0.0.6 or later.
- Run npm --prefix app audit and report any vulnerable dependency the feature touches. Python audit: NONE configured, flag it.
- Assets (fonts, sounds, sprites) need a recorded license in assets/.

### A04 Cryptographic Failures
- Store MODEL_API_KEY with Electron safeStorage only. Pass it to the backend through the spawn environment. Never to the renderer, logs, the repo, or a WebSocket message.
- Generate DESKTOP_TOKEN with crypto.randomBytes(16) or larger per launch. Compare with hmac.compare_digest in Python.
- No custom crypto. Use hashlib.sha256 for sprite cache keys only, never for secrets.

### A05 Injection
- Parameterize every SQLite query with placeholders. No string-built SQL.
- Run ffmpeg with subprocess list arguments, never shell=True, never with player text in arguments.
- Treat transcripts, spoken names, typed names, and object labels as untrusted data. Place them inside JSON fields of model prompts, never as instructions. Ignore any instruction found in them.
- Render all text through React or canvas fillText. Never dangerouslySetInnerHTML.
- Pydantic models use extra="forbid" and strict types. Allowlist fields. Block mass assignment.
- Validate every input on the server: type, format, length, range, allowlist. Enforce schema maxLength locally even if the server ignores it.
- Run every player name and generated text through the local English and Tagalog profanity filter before display, cards, or the reel.

### A06 Insecure Design
- List abuse cases before coding: tampered intents, replayed End Turn, illegal moves, 13th object, extra charms or walls, kubo not first, re-roll spam, speaker spoofing, prompt injection through speech, cost runaway through retries.
- Enforce business limits server-side: 12 objects, 2 charms, 2 walls, one kubo first, stat deltas -1 to +1 with sum 0 or less, ATK cap 3, HP floor 1, cooldowns, one re-roll per unit, max 3 between-turn SAM calls per turn.
- Rate limit cost: cost meter warn at $90 and hard stop at $120 before every paid call. Circuit breaker after 3 failures.
- Model output never writes a number into state. Clamp and validate every model value.

### A07 Authentication Failures
- No accounts exist. The per-launch token is the only authentication. Never persist it to disk or logs.
- No cookies are used, so CSRF tokens do not apply. Require the token on every state-changing request and check Origin on WebSocket connect.
- Regenerate the token on every backend restart. The renderer reads the new one from preload.

### A08 Software or Data Integrity Failures
- Replay proxy uploads to the Files API: H.264 MP4 only, check size before upload, purpose user_data, expires_after 86,400 s, then DELETE right after processing.
- Never deserialize with pickle or eval. JSON only, validated by Pydantic.
- Validate fixtures and saved state on load. Reject unknown fields.

### A09 Security Logging and Alerting Failures
- Log security events: token mismatch, rejected WebSocket, invalid model output (gm_invalid), breaker open, hard stop hit, consent missing.
- Never log MODEL_API_KEY, DESKTOP_TOKEN, the voice handshake, Authorization headers, raw audio, or full frames.

### A10 Mishandling of Exceptional Conditions
- Fail closed. An error never skips consent, the token check, the cost meter, or move validation.
- Roll back the autosave transaction on failure. No swallowed exceptions. The Build Guide's bare except in narrate must catch specific timeout and API errors only.
- Handle timeouts, empty SAM output, missing records, camera busy, mic loss, and backend crash explicitly with the PRD fallbacks.

### Always
- Collect and expose only the data the feature needs. Video stays local. Only warped frames, mask crops, live mic audio, and consented proxy clips leave the laptop.
- Keep secrets out of code, logs, errors, responses, docs, and commits. Run the secret scan from Build Guide 15.2 and check staged files before every commit.
- Stack-specific misuse to avoid: Electron remote content or node access in the renderer, unvalidated IPC, open shell.openExternal, uvicorn bound to all interfaces, string-compared tokens, path traversal through IDs, subprocess with shell=True, trusting LLM JSON without schema and state checks, Contributor mode, WebM recordings sent to SAM, raw video uploads.

## 6. VERIFY
- Add tests: happy path, edge cases, invalid input, unauthorized access (missing or wrong token), abuse cases, failure paths. Deterministic only. Offline only, using fixtures/. Never call paid APIs in tests.
- Rules changes keep the determinism test (E7) at 100% and coverage at 90% or more.
- Run tests, tsc typecheck (strict, via @electron-toolkit/tsconfig), eslint, prettier, and npm audit. Python analyzer and linter: NONE configured. Propose mypy --strict and ruff as an approved dependency change. Zero new failures or violations.
- Use the run skill to confirm UI or integration changes in the real app.
- Docs work: run section 4.7.7.
- Never weaken tests or suppress errors to pass.

## 7. DOCUMENT
- Update the owning doc, docs/product/requirements-index.md status, and CLAUDE.md (state, queue, bugs) in place.
- New decision or resolved contradiction: add or update an ADR.

## 8. REPORT AND COMMIT
- Per changed block: short prose on core logic and control flow.
- Files changed, skills and agents used, verification results with real output.
- Commit message, one line, exact format:
  - Format: `type: Action item here`
  - Example: `docs: Add AI-ready documentation set and project agents`
  - type is a conventional type: feat, fix, refactor, perf, test, docs, chore.
  - No ticket ID. Action item is imperative and specific.
- Auto-commit is allowed. Commit on main (approved) after section 6 passes, once per logical unit of work. Stage only the files this feature changed, by explicit path. Never stage backend/.env, keys, recordings, userdata, or *.sqlite.
- Authorship: EHIBE is the only author. Commit as the configured git user. Never pass --author, never change git config, never add Co-Authored-By or any other trailer, never add AI attribution, "Generated with" lines, or tool names to the message. The commit message is the single line above and nothing else.
- Never amend, never skip hooks, never bypass signing.
- Report each commit hash and message.

## 9. HARD CONSTRAINTS
- No assumptions. Flag every ambiguity.
- Auto-commit allowed per section 8. No co-authoring and no AI attribution, ever. EHIBE is the sole author.
- No other git write operations: push, merge, rebase, stash, reset, checkout, branch creation, tags, amend.
- All agents run on Sonnet 5.5 (claude-sonnet-5-5) at medium effort only.
- No dependency changes or destructive commands without approval. Local environment only.
- Never read, print, or copy backend/.env.
- Zero code comments in new code. Exception: type annotations the analyzer needs.
- No debug code, commented-out blocks, or test data in source.
- No fabricated results in eval.md, playtests.md, or any doc.
- No regressions.

---

## FEATURE DETAILS (write here)
- ID: Not applicable
- Feature:
