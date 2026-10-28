---
title: ADR-0107 Use Decimal for cost math
purpose: Record the decision on use Decimal for cost math
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0107]
sources: [CLAUDE.md#bugs-and-contradictions, docs/FEATURE_PROMPT.md#3-project]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0107: Use Decimal for cost math

Status: Proposed. Raised 2026-10-28. Awaiting EHIBE confirmation.

## Key facts

| Field | Value |
|---|---|
| Status | Proposed |
| Tracks | B7 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Schema choice must be made before any database is created. |

## Context

api_usage.cost_usd and night.cost_usd are REAL in the PRD schema. Float sums drift and the $90 and $120 guardrails need exact comparisons.

## Proposed decision

Compute all costs with Python Decimal from the unit price table. Keep the REAL columns for now, or switch to integer micro-dollars before the first database exists. Decide before Phase 5.

## Consequences

- Closes B7 once accepted and done
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/FEATURE_PROMPT.md#3-project`
