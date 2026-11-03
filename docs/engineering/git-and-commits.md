---
title: Git and commits
purpose: Branch, commit format, authorship and allowed git operations
read_when: [before any commit, before any git command]
canonical_for: [commit format, authorship rule, allowed git operations]
sources: [docs/prompts/FEATURE_PROMPT.md#8-report-and-commit, docs/prompts/FEATURE_PROMPT.md#9-hard-constraints]
status: active
last_verified: 2026-10-28
related: [docs/decisions/ADR-0011-agents-sonnet-medium.md, docs/engineering/definition-of-done.md]
---

# Git and commits

Work happens on main, committed automatically once verification passes. EHIBE is the only author of every commit.

## Key facts

| Rule | Value |
|---|---|
| Branch | main (approved) |
| Format | `type: Action item` |
| Types | feat, fix, refactor, perf, test, docs, chore |
| Ticket IDs | None |
| Author | EHIBE, the configured git user |
| Trailers | None. No Co-Authored-By, no AI attribution, no "Generated with" |
| Who commits | Main session only. Agents never commit |

## Commit rules

- Commit after verification passes, once per logical unit of work.
- Stage files by explicit path. Never `git add -A` blindly.
- Never stage `backend/.env`, `*.key`, recordings, user data or `*.sqlite`.
- Run the secret check on the staged diff before committing.
- The message is exactly one line in the format above.
- Never pass `--author`, never change git config.
- Never amend, never skip hooks, never bypass signing.

## Examples

```text
docs: Add AI-ready documentation set and project agents
feat: Add A4 calibration with manual corner taps
fix: Reject WebSocket connections with a wrong token
test: Add determinism test for resolve_turn
```

## Forbidden operations

push, merge, rebase, stash, reset, checkout, branch creation, tags, amend. The Build Guide's `git tag freeze-nov3` and push steps need an explicit instruction from EHIBE.
