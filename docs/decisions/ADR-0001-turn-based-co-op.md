---
title: ADR-0001 Turn-based co-op survival over real-time RPG
purpose: Record the decision on turn-based co-op survival over real-time RPG
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0001]
sources: [docs/DeskTop_PRD.md#0-document-header, docs/DeskTop_PRD.md#15-rabbit-holes-and-no-gos]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0001: Turn-based co-op survival over real-time RPG

Status: Accepted. Decided 2026-10-25 (PRD v0.3) by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-25 (PRD v0.3) |
| Owner | EHIBE |

## Context

The v0 concept was a real-time pixel art RPG on a desk. Every model call has latency (reasoning models have an initial delay, SAM takes images and uploaded clips, not live streams). A real-time loop would stall on every call and give the GM an unbounded job.

## Decision

Make DeskTop a turn-based co-op survival tactics game named Hanggang Umaga. Every model call fits inside a turn boundary. Players set the pace in PLAYER_PHASE. Combat resolves only at End Turn.

## Consequences

- Latency never breaks play (PG-2)
- GM gets a bounded narration job
- No real-time action (non-goal)
- Night is 8 turns, about 12 to 18 minutes

## Alternatives considered

- Real-time RPG (rejected: latency and cost)
- Real-time with a local-only AI (rejected: loses Meta tooling score)

## Sources

- `docs/DeskTop_PRD.md#0-document-header`
- `docs/DeskTop_PRD.md#15-rabbit-holes-and-no-gos`
