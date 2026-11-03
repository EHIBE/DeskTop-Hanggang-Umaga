---
title: ADR-0111 Packaged build and renderer origin
purpose: Record the decision on the release artifact, Electron fuses and the WebSocket origin of a packaged renderer
read_when: [building the release zip, changing the /ws origin check, changing electron-builder.yml]
canonical_for: [ADR-0111]
sources: [docs/FINALIZATION_PLAN.md#decisions-locked-on-2026-11-03, docs/delivery/release-and-packaging.md, backend/server.py, app/src/main/backend.ts, app/src/main/index.ts]
status: active
last_verified: 2026-11-03
related: [docs/decisions/README.md, docs/delivery/release-and-packaging.md, docs/engineering/environment-and-config.md, docs/decisions/ADR-0103-electron-hardening.md]
---

# ADR-0111: Packaged build and renderer origin

Status: Accepted. Raised 2026-11-03. Accepted 2026-11-03 by EHIBE (D2, D17).

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-11-03 |
| Owner | EHIBE |
| Closes | B12 plan (fuses), packaged origin gap |
| Release artifact | Unsigned Windows zip with the Python backend and venv bundled |

## Context

Judges should run the game without installing Node or Python (D2). The packaged renderer loads from `file://`, and Chromium sends its Origin as `null`. The `/ws` check in `backend/server.py` accepted only the names in `DESKTOP_ALLOWED_ORIGINS`, so a packaged app would sit on Connecting. B12 asked for Electron fuses, which needed a new dependency.

## Decision

- The release is an unsigned zip of the electron-builder output with `backend/` and its venv under `resources/backend` through `extraResources`. Steps: `docs/delivery/release-and-packaging.md`.
- Fuses are set through the electron-builder `electronFuses` config. No `@electron/fuses` dependency.
- Main sets `DESKTOP_PACKAGED=1` for the backend only when `app.isPackaged`. Only then `websocket_origins` adds `null` to the allowed origins. Dev builds still refuse `null`.
- The per-launch token stays required on every connection, packaged or not.

## Consequences

- A packaged renderer can connect while a dev build keeps the strict origin list
- Any local page with a `null` origin can reach the socket only if it also holds the per-launch token, which never leaves main and preload
- The zip is large because it carries OpenCV and numpy
- Follow-up: apply `extraResources` and fuses in Phase 6 and verify the zip on a clean folder

## Alternatives considered

- Serve the renderer from a custom protocol with a real origin (rejected: more main process code and a new protocol handler before the freeze)
- Accept `null` in every build (rejected: weakens the dev check for no gain)
- Add `@electron/fuses` (rejected: new dependency when electron-builder already covers it)

## Sources

- `docs/FINALIZATION_PLAN.md#decisions-locked-on-2026-11-03`
- `docs/delivery/release-and-packaging.md#packaged-origin-issue`
- `backend/server.py` (`websocket_origins`)
