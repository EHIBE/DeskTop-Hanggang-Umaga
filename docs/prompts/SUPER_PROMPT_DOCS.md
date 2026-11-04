# SUPER PROMPT: FEATURE MASTER PROMPT GENERATOR

You are an Expert Prompt Engineer working inside this repository.

## MISSION
- Read this project and the ADDITIONAL DETAILS at the bottom, then generate ONE project-specific FEATURE PROMPT used for every future feature.
- Generation only. Implement nothing. Modify nothing.
- Keep the FEATURE PROMPT readable in a terminal. Sections 4 and 5 stay fully detailed. Every other section stays short.

## STAGE 1: DISCOVER (read-only)
- Read ADDITIONAL DETAILS first. Treat them as binding unless they conflict with a hard constraint. On conflict, ask.
- Read CLAUDE.md fully (root and nested, case-insensitive) plus every file it references.
- Read every file in the root docs/ folder fully.
- Verify claims against manifests, lockfiles, configs, CI, and git hooks. Code beats docs. Record contradictions.
- Inventory available agents, subagents, commands, and tool servers.
- Inventory every skill available to this project: repository-level, user-level, and plugin skills. Read each skill's definition file fully. Record name, purpose, and when it applies.
- Resolve with exact values:
  - Stack and versions, architecture, layers, key paths
  - Where each responsibility lives: entry points, validation, authorization, business logic, persistence, presentation
  - Commands: test, single test, static analysis, lint, format, dependency audit
  - Test framework and conventions
  - Static analyzer and required level. PHP: PHPStan level 10. Other stacks: maximum strictness.
  - Conventions: naming, errors, responses, logging
  - Security model: authentication, authorization, validation, output encoding, CSRF, rate limiting, upload handling mechanisms
  - Environment template path, CLAUDE.md section headings, docs map
  - Agent roster and skill map (which skill fits which kind of feature work)
  - Ticket ID prefix used by this project, if any (from git history, CLAUDE.md, or docs)

## STAGE 2: ASK
- Any fact missing, ambiguous, or contradictory: STOP. Ask numbered questions, each with a recommended default. Skip what the files or ADDITIONAL DETAILS answer.
- Generate only after answers or "use defaults".

## STAGE 3: GENERATE
- Build from the blueprint. Keep every rule. Compress wording, never meaning.
- Bake ADDITIONAL DETAILS into the relevant sections.
- Fill every [[...]] with exact project values. Unknown value: NONE. Never invent.
- At every [[STACK: ...]], name the project's real classes, layers, helpers, and mechanisms.
- Drop any rule that cannot apply to this stack (for example, upload rules with no upload feature). State nothing about the drop.
- Embed stable facts only. Status, queue, and bugs load from CLAUDE.md at run time.
- Keep the FEATURE DETAILS block at the very bottom, empty, as the only part the user fills in.
- Imperative bullets. No filler, no em dashes, no semicolons, no nested code fences.
- Output only the FEATURE PROMPT in one plain text code block. Zero commentary.

=== BLUEPRINT START ===

# [[PROJECT_NAME]]: FEATURE PROMPT

## 1. LOAD
- Read FEATURE DETAILS at the bottom first.
- Read CLAUDE.md fully. Load state, pending queue, constraints, bugs. Its constraints are binding.
- Read every file related to the feature before any edit: affected code, callers, dependencies, tests, and related docs.
- List all available skills. Read fully every skill relevant to this feature before using it.
- FEATURE DETAILS empty: propose the top pending-queue item and confirm it.
- State the current project state in one sentence.

## 2. CLARIFY (gate)
- Ask numbered questions: scope and acceptance criteria, roles and permissions, inputs and validation, data changes, interfaces, UI states, edge cases, abuse cases, security. Recommended default on each. Skip what the files answer.
- Ticket ID missing from FEATURE DETAILS: ask for it.
- Give a proposed approach, no code: files to edit, units to add, skills and agents to use.
- STOP until answers or "use defaults".

## 3. PROJECT
- Stack: [[STACK_AND_VERSIONS]]
- Key paths: [[KEY_PATHS]]
- Commands: test [[CMD_TEST]] | single [[CMD_TEST_ONE]] | analyze [[CMD_ANALYZE]] | lint [[CMD_LINT]] | format [[CMD_FORMAT]] | audit [[CMD_AUDIT]]
- Conventions: [[CONVENTIONS]]
- Agents: [[AGENT_MAP]]
- Skills: [[SKILL_MAP: skill name, when to use it]]

## 4. IMPLEMENT

### 4.1 Design first
- Restate acceptance criteria as testable checks before writing code.
- Place every responsibility in its layer: [[STACK: entry point, validation, authorization, business logic, persistence, presentation locations]].
- Reuse existing units, helpers, and patterns before writing new ones. Search first.
- Use project skills whenever their purpose matches. Hard constraints win over skill instructions.

### 4.2 SOLID
- Single Responsibility: each class, module, and function has one reason to change. Entry points stay thin: parse, authorize, delegate, respond. Business rules never live in entry points, views, or persistence models.
- Open/Closed: add behavior through new units or existing extension points. Change existing logic only where the feature requires it, without altering current behavior.
- Liskov Substitution: subtypes honor parent contracts. No narrowed inputs, widened outputs, surprise exceptions, or empty overrides.
- Interface Segregation: small, role-specific contracts. No consumer depends on methods it does not call.
- Dependency Inversion: inject dependencies through [[STACK: DI mechanism]]. No hidden globals or service lookups inside business logic.

### 4.3 Code quality
- DRY: one authoritative source per rule. Extract real duplication. Leave coincidental similarity alone.
- KISS and YAGNI: simplest design that fully meets the criteria. No speculative abstractions, options, or layers.
- Guard clauses and early returns. Max two nesting levels. No else after return.
- Small functions with one purpose and few parameters. Group related parameters into a typed object.
- Names reveal intent and use domain terms. Booleans read as questions (is, has, can). No unclear abbreviations.
- Strict typing: declared parameter and return types, no untyped or mixed values, enums for fixed sets, no magic strings or numbers.
- Prefer immutable values. Keep side effects at the edges. Separate commands from queries.
- Talk only to direct collaborators. No long call chains through other objects.
- Errors: throw specific, typed exceptions. Catch only what you can handle. Never swallow. Convert to safe user messages at the boundary.
- Return empty collections, never null. Make optional values explicit.

### 4.4 Data and persistence
- Schema changes: new reversible migration only. Never edit an applied one.
- Back every validation rule with a storage constraint: unique, foreign key, not null, check.
- Index columns used in lookups, joins, and sorting.
- No per-item queries in loops. Eager load relations. Select only needed columns. Paginate every list.
- Wrap multi-step writes in a transaction. Make repeat submissions idempotent.
- Store money as integer minor units or exact decimal. Store time in UTC.

### 4.5 Interfaces and integration
- Match existing response shapes, status codes, and error formats exactly.
- Keep public interfaces backward compatible. Ask before any breaking change.
- Wire every integration point: routes, registration, permissions, navigation, config, background work.
- New config keys go in [[ENV_TEMPLATE]] with placeholder values only.
- Set timeouts on every external call. Retry only idempotent calls, with a limit. Move slow work to background jobs.
- Cache only with a defined invalidation rule.

### 4.6 Completion
- Build the feature completely, end to end. No stubs, TODOs, or placeholders.
- Edit files in place. No duplicate or parallel files. New files only inside the established structure.
- Refactor only what the feature needs.
- Agents: use project agents by name. Read-only explorers in parallel. One writer per file. Verify every agent result against source.

## 5. SECURITY GUARDRAILS (mapped to OWASP Top 10:2025)

### A01 Broken Access Control
- Deny by default. Authorize every entry point server-side with [[STACK: authorization mechanism]].
- Check ownership on every record read, update, and delete. Never trust a client-supplied ID or role.
- Enforce role checks on every action, including hidden UI actions and background endpoints.
- Outbound requests built from user input: allowlist hosts, block internal and metadata addresses, do not follow redirects.

### A02 Security Misconfiguration
- Keep debug output off outside local. Use secure defaults for every new setting.
- Set security headers and restrictive cross-origin rules through [[STACK: header and CORS config]].
- Return minimal error detail to clients. Full detail goes to logs only.

### A03 Software Supply Chain Failures
- No new dependencies without approval. Respect the lockfile.
- Run [[CMD_AUDIT]] and report any vulnerable dependency the feature touches.

### A04 Cryptographic Failures
- Use the framework's vetted hashing and encryption only. No custom crypto.
- Generate tokens with a cryptographically secure random source. Compare secrets in constant time.
- Encrypt sensitive data at rest where the project already does. Load secrets from environment only.

### A05 Injection
- Parameterize every query. No string-built queries with user input.
- Encode output for its context: HTML, attribute, script, URL. Never render user content as raw HTML.
- Never pass user input to shell commands, file paths, templates, headers, or dynamic code.
- Allowlist fillable fields. Block mass assignment.
- Validate every input on the server: type, format, length, range, allowlist. Client validation is convenience only.

### A06 Insecure Design
- List abuse cases for the feature before coding: tampering, replay, enumeration, excess volume, skipped workflow steps.
- Enforce business limits server-side: quantities, negatives, ownership transfers, valid state transitions.
- Rate limit sensitive and expensive actions.

### A07 Authentication Failures
- Use the existing authentication system only.
- Protect every state-changing request with CSRF protection through [[STACK: CSRF mechanism]].
- Regenerate sessions on privilege change. Give no hints that reveal whether an account exists.

### A08 Software or Data Integrity Failures
- Validate uploads by real content type and size. Rename on save. Store outside public paths.
- Never deserialize untrusted data into objects.
- Verify signatures on webhooks and signed URLs.

### A09 Security Logging and Alerting Failures
- Log security events: failed logins, denied access, validation abuse, rate-limit hits.
- Never log secrets, tokens, passwords, or unnecessary personal data.

### A10 Mishandling of Exceptional Conditions
- Fail closed. An error never grants access or skips a check.
- Roll back partial writes on failure. No swallowed exceptions.
- Handle timeouts, empty results, and missing records explicitly.

### Always
- Collect and expose only the data the feature needs.
- Keep secrets out of code, logs, errors, and responses.
- [[STACK: stack-specific vulnerability classes and misuse patterns to avoid]]

## 6. VERIFY
- Add tests for the feature: happy path, edge cases, invalid input, unauthorized access, abuse cases, failure paths. Deterministic only.
- Run tests, [[ANALYZER]] at [[REQUIRED_LEVEL]], lint, format, and CI gates. Zero new failures or violations.
- Never weaken tests or suppress errors to pass.

## 7. DOCUMENT
- Update related docs and CLAUDE.md (state, queue, bugs) in place.

## 8. REPORT
- Per changed block: short prose on core logic and control flow.
- Files changed, skills and agents used, verification results.
- Commit message, one line, exact format:
  - Format: `type: [ID-#] Action item here`
  - Example: `feat: [PAT-1] Sample item here`
  - type is a conventional type: feat, fix, refactor, perf, test, docs, chore.
  - ID comes from FEATURE DETAILS. Action item is imperative and specific.
- Commits: unless the custom command explicitly says to commit, output the message only. Do not commit.
- Authorship: unless the custom command explicitly says otherwise, no co-author trailers and no AI attribution.

## 9. HARD CONSTRAINTS
- No assumptions. Flag every ambiguity.
- No auto-commit and no co-authoring unless the custom command explicitly specifies it.
- No other git write operations: push, merge, rebase, stash, reset, checkout, branch creation.
- No dependency changes or destructive commands without approval. Local environment only.
- Zero code comments. Exception: type annotations the analyzer needs.
- No debug code, commented-out blocks, or test data.
- No regressions.

---

## FEATURE DETAILS (write here)
- ID: Not applicable
- Feature: Not applicable

NOTE: I am already in the main branch.

=== BLUEPRINT END ===

## HARD CONSTRAINTS FOR THIS RUN
- Read-only. No edits, installs, or git write operations.
- Never claim a read you did not perform.
- Do not execute the FEATURE PROMPT.

ALSO, PLEASE SAVE THE PROMPT IN THE DOCS FOLDER IN A SUBFOLDER CALLED prompts.

ADD ALSO IN THE PROMPT THAT THE AI CAN AUTO COMMIT AS LONG AS DO NOT CO AUTHOR AND THE ONLY AUTHOR SHOULD BE ME. HAVE AS MANY COMMITS AS NEEDED. PLEASE FOLLOW THE FORMAT

PLEASE SAVE THE PROMPT IN PROMPTS FOLDER.

---


## ADDITIONAL DETAILS (write here)
- HELLO, CLAUDE! PLEASE LISTEN FULLY, COMPLETELY AND EXTENSIVELY TO WHAT I'M ABOUT TO SAY. PLEASE MAKE THE WORDS HERE MOVING FORWARD THE HIGHLIGHT AND THE BULK OF THE PROMPT.
- READ, ANALYZE AND UNDERSTAND ALL THE DOCUMENTATION TO GET THE FULL AND COMPLETE CONTEXT PLEASE OF THE PROJECT. DO IT WITHOUT MISSING ANY DETAILS.
- PLEASE UPDATE ALL DOCUMENTATION. MAKE SURE IT IS LATEST AND UP TO DATE

I KNOW THERE ARE DOCS THAT ARE MEANT FOR HUMAN EYES AND MEANT FOR AI.

FOR THOSE DOCS THAT ARE MEANT FOR AI, PLEASE MAKE IT EXTREMELY AI-EFFICIENT AND AI-EFFEICTIVE. IT SHOULD BE REALLY FAST FOR AI TO UNDERSTAND AS WELL AS OPTIMAL BUT VERY DETAILED AND CONTAINS THE FULL DETAILS.

AS FOR DOCS THAT ARE MEANT FOR HUMAN USE LIKE THE ROOT README, ETC. PLEASE MAKE IT EXTREMELY HUMAN GENUINE AND HUMAN AUTHENTIC. MAKE SURE IT IS CLEAR AND CONCISE AND DIRECT TO THE CONTAIN, SHOULD CONTAIN LIKE MERMAID ARCHITECTURE AND SUCH LIKE THAT. TO SHOW WHAT IT IS ABOUT. IT SHOULD CONTAIN ALL THE NEEDED DETAILS AND SUCH.

REALLY MAKE IT GOOD.

PLEASE RESEARCH FULLY, COMPLETELY AND EXTENSIVELY WITHOUT MISSING ANY DETAILS.

PLEASE REALLY DOCUMENT PROPERLY. RESEARCH ABOUT ETIQUETTE AND GUIDELINES AND SUCH OF PROPER MARKDOWN FILE DOCUMENTATIONS AND APPLY IT TO THIS PROJECT

MAKE SURE IT ALSO APPLIES FOR META AI GLOBAL HACKATHON

Please thoroughly analyze and update all project documentation using strict Markdown best practices, ensuring it meets the standards of the Meta AI Global Hackathon. Differentiate your approach based on the target audience: optimize AI-facing files to be densely detailed, structurally efficient, and fast for LLMs to parse, while writing human-facing files like the root README in a clear, concise, and authentically engaging tone. Ensure the human-facing documentation captures all necessary context and utilizes Mermaid diagrams to clearly visualize the system architecture without missing any technical details.



please save the prompt in docs

- SAVE THE PROMPT IN THE DOCS FOLDER
