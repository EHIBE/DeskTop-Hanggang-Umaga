---
title: ADR-0110 Missing DeskTop_PRD_Prompt.md
purpose: Record the decision on missing DeskTop_PRD_Prompt.md
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0110]
sources: [CLAUDE.md#bugs-and-contradictions, docs/FEATURE_PROMPT.md#3-project]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0110: Missing DeskTop_PRD_Prompt.md

Status: Proposed. Raised 2026-10-28. Awaiting EHIBE confirmation.

## Key facts

| Field | Value |
|---|---|
| Status | Proposed |
| Tracks | B10 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Docs only. |

## Context

Build Guide 0.1 says to paste rule text into the OFFICIAL_RULES slot of DeskTop_PRD_Prompt.md, which is not in the repo.

## Proposed decision

Record Official Rules answers in docs/rules-notes.md and update the affected docs by hand.

## Consequences

- Closes B10 once accepted and done
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/FEATURE_PROMPT.md#3-project`
