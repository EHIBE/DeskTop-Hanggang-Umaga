---
title: ADR-0105 Warped frame size is 1200x800 at 20 px per cm
purpose: Record the decision on warped frame size is 1200x800 at 20 px per cm
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0105]
sources: [CLAUDE.md#bugs-and-contradictions, docs/FEATURE_PROMPT.md#3-project]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0105: Warped frame size is 1200x800 at 20 px per cm

Status: Proposed. Raised 2026-10-28. Awaiting EHIBE confirmation.

## Key facts

| Field | Value |
|---|---|
| Status | Proposed |
| Tracks | B5 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Docs and config only. |

## Context

Build Guide 2.2 sets PX_PER_CM = 20 and a 60 x 40 cm play area, giving 1200 x 800. PRD box prompt examples use w=1280, h=853 and PRD says the renderer gets 960x540 frames while Build Guide 3.3 resizes to 960x640.

## Proposed decision

Use 20 px per cm and play area size times 20 for the warped frame. Stream to the renderer at 960 px wide keeping the aspect ratio (960x640 for the default area). Keep the value in backend/config.py.

## Consequences

- Closes B5 once accepted and done
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/FEATURE_PROMPT.md#3-project`
