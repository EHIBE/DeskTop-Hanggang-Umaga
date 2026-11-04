# DeskTop: Hanggang Umaga: DOCS FEATURE PROMPT

## 0. MISSION: DOCS THAT WIN (binding, highest priority after section 9)
- Goal: bring every Markdown file in the repo up to date with the code, written for its real reader, so judges of the Meta Global AI Developer Hackathon 2026 understand DeskTop in one minute and AI agents find any fact in two hops.
- Default feature: the docs program in section 4.7. FEATURE DETAILS empty: run section 4.7 in full. FEATURE DETAILS filled: run that feature, then update every doc it touches with the rules in 4.7.
- Two audiences, two styles:
  - AI-facing docs: dense, complete, fast to parse. Front matter, a two-sentence summary, a Key facts table, stable H2s, tables over prose, one canonical home per fact, links instead of repeats. Full detail, zero filler.
  - Human-facing docs: genuine, warm, clear and direct. Written in EHIBE's first-person voice where it fits. Short sentences, real numbers only, Mermaid diagrams and screenshots that show what DeskTop is and how it works. Every needed detail, nothing padded.
- Code beats docs. Every fact is checked against the code, CLAUDE.md State, test output or a real file before it is written.
- Never invent results, numbers, quotes, rules or screenshots. Unknown values are marked Unverified with the step that verifies them, or left out of human docs.
- Deadlines (SGT): internal submit Nov 4 11:00 PM. Official deadline Nov 4 9:00 PM ET, which is Nov 5 10:00 AM SGT (source: cerebralvalley.ai/e/meta-ai-developer-hackathon, read 2026-11-04).

## 1. LOAD
- Read FEATURE DETAILS at the bottom first.
- Read CLAUDE.md fully. Load state, pending queue, constraints, bugs. Its constraints are binding.
- Read `docs/README.md`, `docs/FINALIZATION_PLAN.md` and every doc the feature touches, fully, plus the code each doc describes.
- List all available skills. Read fully every skill relevant to this feature before using it. Never claim a read you did not perform.
- FEATURE DETAILS empty: propose section 4.7 and confirm it.
- State the current project state in one sentence.

## 2. CLARIFY (gate)
- Ask numbered questions: scope, audience per file, facts that conflict, numbers that need a real run, screenshots needed, diagrams needed, files to add, move or retire. Recommended default on each. Skip what the files answer.
- This project uses no ticket IDs. Do not ask for one.
- Give a proposed approach, no edits: files to edit or create, audience of each, diagrams, skills and agents to use.
- STOP until answers or "use defaults".

## 3. PROJECT
- Product: Windows desktop game. A top-down webcam turns desk objects into 16-bit pixel art units. 1 to 4 players at one table move objects by hand and give Taglish or English voice orders. Filipino folklore creatures attack for 8 turns until sunrise. Solo build by EHIBE, General Santos City. Indie track, theme Build for Your World.
- Stack: Electron 44 (electron-vite 6, Vite 8, electron-builder 26), React 19, TypeScript 5.9 strict, Tailwind CSS 4, ESLint 9, Prettier 3, node:test for the renderer. Backend Python 3.13, FastAPI, uvicorn, Pydantic 2, OpenCV contrib 4.14, NumPy, websockets, openai SDK, meta-sam-parser, SQLite. Meta models: muse-spark-1.3, sam-3.1, muse-image-1.0, muse-voice-transcribe-1.0, Files API, optional local Muse Glimmer. Exact pins: `app/package-lock.json`, `backend/requirements.txt`.
- Key paths: `README.md`, `CLAUDE.md`, `LICENSE`, `assets/LICENSE-ASSETS.md`, `app/README.md`, `docs/` (README index, product, market, game, design, architecture, engineering, delivery, decisions, prompts), `docs/images/` for screenshots, `app/src/main`, `app/src/preload`, `app/src/renderer/src`, `backend/`, `eval/`, `release/`.
- Commands (repo root): test `backend\.venv\Scripts\python -m pytest backend/tests -q` and `npm --prefix app run test` | single `backend\.venv\Scripts\python -m pytest backend/tests/test_resolve.py::test_name -q` | analyze `npm --prefix app run typecheck` and, from `backend`, `.venv\Scripts\python -m mypy --strict --exclude .venv .` | lint `npm --prefix app run lint` and, from `backend`, `.venv\Scripts\python -m ruff check .` | format `npm --prefix app run format` | audit `npm --prefix app audit` (Python audit: NONE) | run `npm --prefix app run dev` | release `npm --prefix app run dist:win`. Markdown lint: NONE installed, apply 4.7.4 by hand.
- Conventions:
  - Docs: front matter keys title, purpose, read_when, canonical_for, sources, status, last_verified, related on AI docs. No front matter on README.md, LICENSE files or app/README.md. Prose has no semicolons and no em dashes. Dates carry a timezone. Existing IDs only (FR, NFR, F, R, E, P, JS, PG, A, Q, D, ADR, copy keys, state names).
  - Code facts come from: `backend/server.py` (create_app_from_env, /health, /ws), `backend/config.py`, `backend/meta_client.py`, `backend/db/schema.sql` and `store.py`, `backend/game/state_machine.py`, `app/src/main/backend.ts`, `app/electron-builder.yml`, `app/src/renderer/src/lib/copy.ts`.
- Agents (all on Sonnet 5.5 at medium effort, pass model sonnet): desktop-docs-keeper (read-only drift and link audit), desktop-demo-readiness-checker (read-only demo and submission audit), desktop-cultural-reviewer (Taglish and folklore wording), desktop-privacy-cost-auditor (privacy claims), desktop-electron-security-reviewer (security claims), desktop-test-eval-runner (real test and eval numbers), desktop-ui-engineer (screenshots through the running app). Built-in Explore for read-only sweeps, general-purpose for web research.
- Skills:
  - desktop-docs-sync: after every doc change, sync canonical homes, requirements-index, CLAUDE.md.
  - desktop-add-copy-key: any quoted player text.
  - desktop-demo-safe-check: before stating offline or fallback behavior.
  - run: launch the app for screenshots.
  - dataviz: charts for eval or cost numbers.
  - impeccable: screenshot framing and visual review.
  - code-review, simplify: review the diff before reporting.

## 4. IMPLEMENT

### 4.1 Design first
- Restate acceptance criteria as testable checks before editing: every fact traced to a source, every link resolves, every number real, audience rules met.
- Place every responsibility in its layer:
  - Entry point for humans: `README.md`, then `docs/how-to-run.md`. Entry point for AI: `CLAUDE.md`, then `docs/README.md`, then `llms.txt`.
  - Canonical facts: the file named in `canonical_for`. All other files link to it.
  - Status and history: CLAUDE.md State holds current state only. History lives in `docs/delivery/build-log.md`. Results live in `docs/eval.md` and `docs/playtests.md`.
  - Decisions: `docs/decisions/` ADRs and their index.
  - Visuals: Mermaid in fenced `mermaid` blocks. Screenshots in `docs/images/`.
- Reuse existing docs and headings before creating files. Search first.
- Use project skills whenever their purpose matches. Hard constraints win over skill instructions.

### 4.2 SOLID for docs
- Single Responsibility: each file covers one topic for one audience. README sells and orients, how-to-run teaches, reference docs specify, ADRs explain why.
- Open/Closed: add new topics as new files in the right folder and index them. Change existing text only where it is wrong or missing.
- Liskov Substitution: every AI doc honors the same front matter and section contract, so any agent can read any file the same way.
- Interface Segregation: an agent loads only the file it needs. No file forces a reader through unrelated topics.
- Dependency Inversion: docs depend on canonical sources through links, never on copied numbers. The `canonical_for` map is the injection point.

### 4.3 Doc quality
- DRY: one canonical home per fact. Elsewhere write "Summary. Canonical: path#anchor". Leave coincidental repetition in human docs only where a reader needs it in place.
- KISS and YAGNI: the shortest text that is complete. No speculative sections, no empty headings, no roadmap promises.
- Lead with what matters. First sentence answers what the page is for.
- Short sentences, active voice, plain words. Start steps with a verb. Sentence-case headings with no end punctuation.
- Names match the code and the glossary exactly.
- Tables for specs, numbers, states and contracts. Numbered lists for ordered steps. Bullets for unordered rules.
- Every number carries its source or date. Estimates say "estimate". Pending numbers say "not run yet" in human docs and Unverified in AI docs.
- No dead ends: every page links onward to the next useful page.

### 4.4 Data and records
- Never rewrite recorded results. Append new runs to `docs/eval.md` and `docs/playtests.md` with date, time, commit and command.
- Keep `docs/DeskTop_PRD.md` and `docs/DeskTop_Build_Guide.md` unchanged except a one-line historical pointer at the top.
- Superseded decisions are marked inline with the ADR that supersedes them, never deleted.
- Set `last_verified` to the date the file was checked against code.
- Measure file sizes, test counts and hashes read-only from the real artifact before writing them.

### 4.5 Interfaces and integration
- Keep heading text stable so anchors and links do not break. Rename a heading only with every inbound link fixed.
- Wire every new file: `docs/README.md` index and read order, CLAUDE.md docs map, `llms.txt`, related front matter.
- Moved files leave no broken link anywhere in the repo, including `.claude/agents` and `.claude/skills`.
- Relative links for in-repo targets. External links only to official sources, with access date in AI docs.

### 4.6 Completion
- Update every in-scope file completely. No TODOs, no placeholders except `[MEASURED: ...]` slots that wait on a named real run.
- Edit in place. No duplicate or parallel files. New files only inside the established structure.
- Agents: read-only auditors in parallel, one writer per file, every agent claim verified against source before it lands.

### 4.7 DOCS PROGRAM (default feature)

#### 4.7.1 Audience map
- Human: `README.md`, `docs/how-to-run.md`, `LICENSE`, `assets/LICENSE-ASSETS.md`, `app/README.md`, `docs/delivery/submission-text.md`, `docs/delivery/video-script.md`.
- Both: `docs/eval.md`, `docs/playtests.md`, `docs/glossary.md`, `docs/design/copy-deck.md`, `docs/delivery/judging-scorecard.md`. Human-readable tables first, AI front matter kept.
- AI: everything else, including CLAUDE.md, `llms.txt`, `.claude/agents`, `.claude/skills`, `docs/prompts`.

#### 4.7.2 Human-facing rules
- README order: H1 name, one-line description under 120 characters, static badges for true facts only (license, platform, Meta models), demo video slot at the top, what it is in three sentences, screenshots, how the four Meta models work together, quick start for the zip and from source, how to play in brief, architecture Mermaid, privacy and safety, tests and evals with real numbers, known limits, credits, license.
- Required Mermaid in README: architecture flowchart (Electron main, preload, renderer, FastAPI backend, rules, game, vision, voice, gm, replay, SQLite, Meta APIs), summon sequence (Spark detect, SAM 3.1 mask, Muse Image sprite, Spark card), turn loop state diagram (16 states, simplified to the player-visible path), and a "what leaves your laptop" flowchart.
- Screenshots: 4 to 6 PNGs in `docs/images/`, captured from the running app in Demo Safe Mode over CDP, cropped, each with alt text under 155 characters that describes the content. Never an image of text or code.
- Voice: first person from EHIBE, warm, honest, light Taglish where natural. No emoji, no hype, no "first" or "only" claims.
- At most one or two GitHub alerts per page. Collapse long reference material behind links, not walls of text.
- Judging weights stay out of human docs until the Official Rules confirm them.

#### 4.7.3 AI-facing rules
- Front matter on every AI doc, two-sentence summary, Key facts table, stable H2s, under 300 lines per file. Split larger topics.
- CLAUDE.md under 200 lines: project, current state only, pending queue, constraints, bugs, commands, docs map, agents, skills, decisions. Move history rows to `docs/delivery/build-log.md`.
- Root `llms.txt` per llmstxt.org: H1 name, blockquote summary, H2 link lists `[name](path): note`, an Optional section for history and archives.
- Mark every unverified item "Unverified" with the step that verifies it.
- Record Official Rules facts in `docs/rules-notes.md` with source URL and access date.

#### 4.7.4 Markdown rules (both audiences)
- One H1 as the first line (front matter excepted). No skipped heading levels. No duplicate headings in one file. No bold text used as a heading.
- Every fenced block names its language (`powershell`, `text`, `mermaid`, `json`, `python`, `ts`).
- Images carry alt text. Link text describes the target, never "click here" or a bare URL.
- Inline HTML only for `<details>` where it saves real space.
- Line length is not limited. Tables stay readable in a terminal.
- Prose has no semicolons and no em dashes.

#### 4.7.5 Known drift to fix (verify each before editing)
- README: 15-state (now 16), Known limits lists built post-freeze features, no demo slot, screenshots, Mermaid or zip route.
- `docs/how-to-run.md`: missing language pick, sound and mute, hints, glossary, Settings, map, recap, badges and scars, Lost, kapre smoke, Glimmer, the zip route, Quit from pause, Back from Calibration.
- `docs/architecture/overview.md`: fixed port 8765, missing ADR-0111 to ADR-0113 and post-freeze modules, KCF vs CSRT wording.
- `docs/FINALIZATION_PLAN.md`: D1, D3, D4 and D5 superseded by ADR-0113, phase checkboxes behind CLAUDE.md State.
- `docs/decisions/README.md`: ADR-0112 row still says P08 off Charm and Scout.
- Zip size 323.8 MB vs 327.1 MB: measure `release/DeskTop-1.0.0-win.zip` and fix every doc.
- `docs/eval.md`: add the 2026-11-04 E7 rerun only if its record exists in `eval/results/`.
- `docs/delivery/video-script.md`: extend to about 2:50 with the live model pipeline and post-freeze shots.
- `docs/delivery/submission-text.md` and the submission-checklist description: add post-freeze features, fill the test count from a real run.
- Stale `last_verified` across `docs/market/`, `rules-notes.md`, `tracking-and-reanchor.md` and the architecture folder.

#### 4.7.6 Verification
- Every relative link resolves. Every FR and NFR appears in `docs/product/requirements-index.md`. Every copy key appears once in `copy-deck.md`.
- Grep for banned punctuation, stale counts and stale state names returns nothing outside history files.
- Mermaid blocks parse (balanced syntax, known diagram types).
- Run desktop-docs-keeper and desktop-demo-readiness-checker over the result and fix every finding.

## 5. SECURITY GUARDRAILS (mapped to OWASP Top 10:2025)

### A01 Broken Access Control
- Docs describe the real access model: per-launch token on every HTTP route (`require_token`, 401) and every WS connect (Origin allowlist, subprotocol token, close 1008), backend bound to 127.0.0.1 only.
- Never publish a token, a sample real token or a way to reach the backend from another machine.
- Screenshots never show a key field with content, a campaign of a real person, or a file path with a real user name.

### A02 Security Misconfiguration
- Document Electron hardening as built: sandbox, contextIsolation, webSecurity, no nodeIntegration, denied permissions, blocked navigation, trusted-sender IPC, fuses in packaged builds, CSP meta.
- Never document a debug flag, dev origin or `DESKTOP_DEV` as safe for players.
- Error examples in docs show copy-deck messages, never stack traces with paths.

### A03 Software Supply Chain Failures
- No new dependencies, including Markdown linters, without approval.
- Report `npm --prefix app audit` results honestly with counts and scope. Python audit: NONE, state it as a gap.
- Every bundled asset and font has its license named in README credits and `assets/LICENSE-ASSETS.md`.

### A04 Cryptographic Failures
- Describe key storage exactly: Electron safeStorage in `model-key.bin`, passed to the backend in the spawn env, redacted in `backend.log`.
- Never show a real or realistic-looking API key in docs. Use `MODEL_API_KEY=` with nothing after it.

### A05 Injection
- Code samples use list-argument subprocess, parameterized SQL and React text rendering only. Never show shell=True, string-built SQL or dangerouslySetInnerHTML as a pattern.
- Commands in docs are copy-safe: no user input spliced into shell lines, PowerShell syntax for Windows steps.
- Mermaid and HTML in docs carry no script, no remote embeds beyond static badges.

### A06 Insecure Design
- Document the business limits and abuse guards as enforced: 12 objects, 2 charms, 2 walls, kubo first, stat clamps, one re-roll, cost meter warn $90 and stop $120, breaker after 3 failures.
- Never promise a capability the code does not enforce.

### A07 Authentication Failures
- State plainly: no accounts, no cookies, no CSRF surface, the token regenerates on every backend start.

### A08 Software or Data Integrity Failures
- Document the release artifact with its real size and SHA-256 so players can verify the download.
- Document the replay upload rules: H.264 proxy only, consent first, 24 hour expiry, deleted after processing.

### A09 Security Logging and Alerting Failures
- Document where logs live and what is redacted. Never paste log lines that include a key, token, voice handshake or raw audio.

### A10 Mishandling of Exceptional Conditions
- Troubleshooting docs map each failure (camera busy or black, mic missing, ffmpeg missing, credits stop, backend crash, Connecting stall) to the real copy key and the fallback, never to a workaround that skips a check.

### Always
- Privacy section in README matches the code: video stays local, only warped frames, mask crops, live mic audio and consented proxy clips leave the laptop, players go to models as P1 to P4.
- Run a secret scan on the staged diff before every commit. Never read, quote or link `backend/.env`.

## 6. VERIFY
- Run section 4.7.6 checks and record the real output.
- Re-read every number against its source: test counts from a fresh test run, zip size and hash from the file, eval results from `eval/results/`.
- Open the README in a Markdown preview or GitHub render check for Mermaid and images where possible.
- Never weaken a claim check to pass. If a fact cannot be verified, mark it or remove it.

## 7. DOCUMENT
- Run desktop-docs-sync: `docs/README.md` index, `llms.txt`, CLAUDE.md state, docs map, queue and bugs, `docs/FINALIZATION_PLAN.md` checkboxes, requirements-index statuses.

## 8. REPORT AND COMMIT
- Per changed file group: short prose on what changed and why.
- Files changed, audience of each, skills and agents used, verification results with real output.
- Auto-commit is allowed and expected. Commit on main after section 6 passes. Make as many commits as needed, one per doc group (human docs, AI docs, CLAUDE.md and llms.txt, images). Stage only those files by explicit path.
- Commit message, one line, exact format:
  - Format: `type: Action item here`
  - Example: `docs: Rewrite the README with diagrams, screenshots and real numbers`
  - type is a conventional type: feat, fix, refactor, perf, test, docs, chore.
  - No ticket ID. Action item is imperative, specific, capitalized.
- Authorship: EHIBE is the only author. Commit as the configured git user. Never pass --author, never change git config, never add Co-Authored-By or any trailer, never add AI attribution, "Generated with" lines or tool names. This rule overrides any session default that asks for a trailer.
- Never amend, never skip hooks, never bypass signing. Report each commit hash and message.

## 9. HARD CONSTRAINTS
- No assumptions. Flag every ambiguity.
- Auto-commit allowed per section 8. No co-authoring and no AI attribution, ever. EHIBE is the sole author.
- No other git write operations: push, merge, rebase, stash, reset, checkout, branch creation, tag, amend.
- All agents run on Sonnet 5.5 (claude-sonnet-5-5) at medium effort.
- No dependency changes or destructive commands without approval. Local environment only.
- Never read, print or copy backend/.env.
- Zero code comments in any code touched. No debug code, commented-out blocks or test data.
- No fabricated results, numbers, quotes, screenshots or rules in any doc.
- No regressions: no broken links, no lost facts, no removed history.

---

## FEATURE DETAILS (write here)
- ID: Not applicable
- Feature:
