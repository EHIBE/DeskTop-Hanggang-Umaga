---
title: ADR-0005 Solid key-color background plus local chroma key for sprites
purpose: Record the decision on solid key-color background plus local chroma key for sprites
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0005]
sources: [docs/DeskTop_PRD.md#sprite-pipeline, docs/architecture/sprite-pipeline.md]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0005: Solid key-color background plus local chroma key for sprites

Status: Accepted. Decided 2026-10-25 (PRD v0.2) by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-25 (PRD v0.2) |
| Owner | EHIBE |

## Context

Muse Image output background is always opaque, so transparent sprites cannot be requested.

## Decision

Ask for a solid #FF00FF background (or #00FF00 when the object hue is within 30 degrees of magenta), key it out locally, erode 1 px, quantize to Gabi 16 plus 8 object colors, add a 1 px outline. Fall back to the other key color, then a SAM cutout, then the placeholder sprite.

## Consequences

- Works with an opaque-only model
- Needs a validation step (alpha coverage 15% to 90%)
- Placeholder sprites always exist first

## Alternatives considered

- Transparent generation (rejected: not supported)

## Sources

- `docs/DeskTop_PRD.md#sprite-pipeline`
- `docs/architecture/sprite-pipeline.md`
