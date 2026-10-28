---
title: ADR-0106 Constant-time token compare and an injected Meta client
purpose: Record the decision on constant-time token compare and an injected Meta client
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0106]
sources: [CLAUDE.md#bugs-and-contradictions, docs/FEATURE_PROMPT.md#3-project]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0106: Constant-time token compare and an injected Meta client

Status: Proposed. Raised 2026-10-28. Awaiting EHIBE confirmation.

## Key facts

| Field | Value |
|---|---|
| Status | Proposed |
| Tracks | B6 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Code pattern only. |

## Context

Build Guide 3.3 checks the token with != and 1.2 creates a module-level OpenAI client. The feature prompt requires hmac.compare_digest and dependency injection.

## Proposed decision

Compare tokens with hmac.compare_digest. Create the client in one factory and inject it into services through FastAPI Depends and constructors. Tests inject fixture fakes.

## Consequences

- Closes B6 once accepted and done
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/FEATURE_PROMPT.md#3-project`
