---
title: ADR-0103 Harden the Electron window and preload
purpose: Record the decision on harden the Electron window and preload
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0103]
sources: [CLAUDE.md#bugs-and-contradictions, docs/prompts/archive/FEATURE_PROMPT_docs_program.md#3-project]
status: active
last_verified: 2026-11-03
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0103: Harden the Electron window and preload

Status: Accepted. Raised 2026-10-28. Accepted 2026-10-28 by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Tracks | B3 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Code change in app/src/main and app/src/preload. No dependency change. |

## Context

The scaffold sets sandbox: false, exposes the full electronAPI and an empty api object through contextBridge, and calls shell.openExternal for any URL. NFR-24 and PRD section 12 say preload exposes only the port and token.

## Decision

Set sandbox: true, contextIsolation: true, nodeIntegration: false. Expose only a frozen `window.desktop` bridge. Allowlist https URLs for shell.openExternal. Remove the ping IPC test handler. Add connect-src for the backend to the CSP. The port is a wildcard because main picks a free port per launch.

Amendment 2026-10-28 (M3): KeySetup needs to save the key through main, so the preload also exposes `getKeyStatus()` and `saveKey(key)`. Both are sender-checked in main. The key passes through the renderer only while the player pastes it.

Amendment 2026-11-03: the bridge is `getConfig`, `getKeyStatus`, `saveKey` and `showReel`. Main accepts only `reel_<name>.mp4`, checks the sender and refuses paths outside the campaign recordings folders. `@electron-toolkit/preload` was removed on 2026-11-03 (B13). The preload uses `contextBridge` and `ipcRenderer` from `electron` directly.

## Consequences

- Closes B3 once accepted and done
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/prompts/archive/FEATURE_PROMPT_docs_program.md#3-project`
