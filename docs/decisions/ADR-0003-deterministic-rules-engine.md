---
title: ADR-0003 Deterministic rules engine is authoritative
purpose: Record the decision on deterministic rules engine is authoritative
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0003]
sources: [docs/DeskTop_PRD.md#13-ai-behavior-evaluation-and-guardrails, docs/game/combat-math.md]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0003: Deterministic rules engine is authoritative

Status: Accepted. Decided 2026-10-25 (PRD v1.0) by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-25 (PRD v1.0) |
| Owner | EHIBE |

## Context

An improvising GM would invent units, numbers and rules, and outcomes would feel unfair. Judges need reproducible results.

## Decision

A pure Python rules engine in backend/rules with no I/O, clock, or randomness decides every number: movement legality, range, damage, HP, cooldowns, spawns, enemy AI, win and lose. Muse Spark only picks class and power from enums and narrates listed events. Enemy intents are telegraphed.

## Consequences

- Same inputs give the same events (E7)
- Easy unit tests, 90% coverage target
- GM output has no state-changing numbers
- No dice combat (no-go)

## Alternatives considered

- GM decides outcomes (rejected: hallucination, unfair)
- Dice with seeded RNG (rejected: less explainable, PG-3)

## Sources

- `docs/DeskTop_PRD.md#13-ai-behavior-evaluation-and-guardrails`
- `docs/game/combat-math.md`
