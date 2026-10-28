---
title: ADR-0103 Harden the Electron window and preload
purpose: Record the decision on harden the Electron window and preload
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0103]
sources: [CLAUDE.md#bugs-and-contradictions, docs/FEATURE_PROMPT.md#3-project]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0103: Harden the Electron window and preload

Status: Proposed. Raised 2026-10-28. Awaiting EHIBE confirmation.

## Key facts

| Field | Value |
|---|---|
| Status | Proposed |
| Tracks | B3 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Code change in app/src/main and app/src/preload. No dependency change. |

## Context

The scaffold sets sandbox: false, exposes the full electronAPI and an empty api object through contextBridge, and calls shell.openExternal for any URL. NFR-24 and PRD section 12 say preload exposes only the port and token.

## Proposed decision

Set sandbox: true, contextIsolation: true, nodeIntegration: false. Expose only a typed object with port and token. Allowlist https URLs for shell.openExternal. Remove the ping IPC test handler. Add connect-src for the backend to the CSP.

## Consequences

- Closes B3 once accepted and done
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/FEATURE_PROMPT.md#3-project`
