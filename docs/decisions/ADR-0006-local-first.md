---
title: ADR-0006 Local-first app with no cloud hosting
purpose: Record the decision on local-first app with no cloud hosting
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0006]
sources: [docs/DeskTop_PRD.md#10-non-functional-requirements, docs/engineering/security-and-privacy.md]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0006: Local-first app with no cloud hosting

Status: Accepted. Decided 2026-10-25 (PRD v0.2) by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-25 (PRD v0.2) |
| Owner | EHIBE |

## Context

A FastAPI server on Render and MySQL on Aiven were planned. The game is played at one table on one laptop. Cloud hosting adds risk, cost and privacy exposure with no player value.

## Decision

The FastAPI backend runs on 127.0.0.1 as a child process of Electron. Full video, audio and the database stay on the laptop. Only single warped frames, mask crops, live mic audio and a consented highlight proxy clip go to Meta.

## Consequences

- No accounts, no login, no cloud sync (non-goals)
- Per-launch token protects the local server
- Privacy story is simple to explain

## Alternatives considered

- Render plus Aiven (rejected)

## Sources

- `docs/DeskTop_PRD.md#10-non-functional-requirements`
- `docs/engineering/security-and-privacy.md`
