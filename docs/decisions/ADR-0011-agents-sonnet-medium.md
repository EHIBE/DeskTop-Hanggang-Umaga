---
title: ADR-0011 All AI agents run on Sonnet 5.5 at medium effort
purpose: Record the decision on all AI agents run on Sonnet 5.5 at medium effort
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0011]
sources: [docs/FEATURE_PROMPT.md, docs/engineering/git-and-commits.md]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0011: All AI agents run on Sonnet 5.5 at medium effort

Status: Accepted. Decided 2026-10-28 by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-28 |
| Owner | EHIBE |

## Context

EHIBE set a single model and effort for every agent used on this project to keep cost and behavior predictable.

## Decision

Every agent, built-in, user-level or project-level, runs on Sonnet 5.5 (claude-sonnet-5-5) at medium effort. Project agent files set model: sonnet and effort: medium. Every Agent call passes model sonnet. Agents never commit. EHIBE is the sole commit author with no co-author trailers or AI attribution.

## Consequences

- Predictable cost and behavior
- One writer per file, main session verifies agent output
- Commit policy lives in engineering/git-and-commits.md

## Alternatives considered

- Mixed models per agent (rejected)

## Sources

- `docs/FEATURE_PROMPT.md`
- `docs/engineering/git-and-commits.md`
