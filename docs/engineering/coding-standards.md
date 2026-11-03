---
title: Coding standards
purpose: Python and TypeScript rules for structure, naming, typing, errors and style
read_when: [writing or reviewing any code]
canonical_for: [code conventions, naming, error handling rules, style tool settings]
sources: [docs/prompts/FEATURE_PROMPT.md#4-implement, app/.prettierrc.yaml, app/.editorconfig, app/eslint.config.mjs]
status: active
last_verified: 2026-11-03
related: [docs/architecture/backend-modules.md, docs/architecture/frontend-modules.md, docs/engineering/definition-of-done.md]
---

# Coding standards

Short summary of the rules in `prompts/FEATURE_PROMPT.md` section 4 applied to this stack. When the two differ, the prompt wins.

## Key facts

| Fact | Value |
|---|---|
| Comments | Zero code comments in new code (type annotations allowed) |
| TS style | Prettier singleQuote, no semicolons, printWidth 100, trailingComma none, 2 spaces, LF |
| Python style | PEP 8 naming, full type hints. No linter configured yet (propose ruff, mypy --strict) |
| Nesting | Max two levels, guard clauses, no else after return |

## Shared rules

- One responsibility per module and function. Entry points parse, authorize, delegate, respond.
- Reuse before writing. Search the repo first.
- Names use domain terms: kubo, intent, telegraph, re-anchor, night_unit. Booleans start with is, has, can.
- No magic numbers or strings. Constants in `backend/config.py`, enums for fixed sets.
- Return empty collections, never null for lists. Optional values explicit.
- Immutable values preferred. Side effects at the edges. Commands separate from queries.
- No debug code, no commented-out blocks, no test data in source.

## Python

| Rule | Detail |
|---|---|
| Types | Annotate every parameter and return. No `Any`. `Literal` or `Enum` for states, classes, powers, moods, actions |
| Data | Pydantic models at boundaries (`extra="forbid"`). Frozen dataclasses inside rules |
| Rules engine | Pure functions, no I/O, no time, no randomness |
| Injection | FastAPI `Depends` and constructors. No module-level clients |
| Errors | Specific exception classes. Catch only what you handle. Never bare `except` |
| Async | `asyncio.wait_for` for timeouts. Blocking OpenCV loops in threads |
| SQL | `sqlite3` with `?` placeholders only |
| Subprocess | List args, never `shell=True` |
| Secrets | Read from env. Never log |

## TypeScript and React

| Rule | Detail |
|---|---|
| Types | Strict (from @electron-toolkit/tsconfig). No `any`. Message types mirror Pydantic |
| Components | Function components with explicit `React.JSX.Element` return types |
| Imports | `@renderer/*` alias |
| Text | Only from `lib/copy.ts` |
| Rendering | No `dangerouslySetInnerHTML`. Canvas `fillText` for board text |
| Hooks | Follow eslint-plugin-react-hooks rules |
| Electron | No Node APIs in renderer. Preload exposes only the frozen `window.desktop` bridge (`getConfig`, `getKeyStatus`, `saveKey`, `showReel`) |

## Errors and messages

- Players see copy-deck lines only. Never raw errors or model output.
- Log full detail locally. Never log the key, token, voice handshake, raw audio or full frames.

## Files

- Follow the PRD folder tree. New files only inside it.
- Edit in place. No duplicate or parallel files.
