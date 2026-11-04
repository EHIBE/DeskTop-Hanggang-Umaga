---
title: ADR-0108 Replace scaffold placeholders
purpose: Record the decision on replace scaffold placeholders
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0108]
sources: [CLAUDE.md#bugs-and-contradictions, docs/prompts/archive/FEATURE_PROMPT_docs_program.md#3-project]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0108: Replace scaffold placeholders

Status: Accepted. Raised 2026-10-28. Accepted 2026-10-28 by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Tracks | B8 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Do before the Windows build in Phase 15. |

## Context

app/package.json name is app with author example.com. electron-builder appId is com.electron.app, productName app, executableName app, and publish points to https://example.com/auto-updates. Window title is Electron.

## Decision

Set productName DeskTop, a real appId, the window title, and remove the publish block until a real update target exists.

## Consequences

- Closes B8 once accepted and done
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/prompts/archive/FEATURE_PROMPT_docs_program.md#3-project`
