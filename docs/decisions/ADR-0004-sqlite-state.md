---
title: ADR-0004 SQLite for game state, Muse Glimmer only as a Could
purpose: Record the decision on SQLite for game state, Muse Glimmer only as a Could
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0004]
sources: [docs/DeskTop_PRD.md#sqlite-schema, docs/architecture/data-model.md]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0004: SQLite for game state, Muse Glimmer only as a Could

Status: Accepted. Decided 2026-10-25 (PRD v0.2) by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-25 (PRD v0.2) |
| Owner | EHIBE |

## Context

Campaigns must save after every turn and restore after a crash. A 30B language model is not a database and needs a large GPU.

## Decision

Store all state in local SQLite (schema in backend/db/schema.sql). Autosave is one transaction at CHECK_END. Muse Glimmer may write recap text as a Could (F19).

## Consequences

- Crash restore at turn start (FR-41)
- Database lives in the Electron user data folder
- Glimmer is optional and labeled when used
- Amendment: Glimmer recap built 2026-11-04, off until DESKTOP_GLIMMER_URL is set (ADR-0113)

## Alternatives considered

- Glimmer as memory (rejected)
- Cloud MySQL on Aiven (rejected, see ADR-0006)

## Sources

- `docs/DeskTop_PRD.md#sqlite-schema`
- `docs/architecture/data-model.md`
