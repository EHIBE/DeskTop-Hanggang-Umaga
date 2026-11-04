---
title: ADR-0002 Hybrid tracking with OpenCV between turns, SAM at End Turn, SAM video for the replay
purpose: Record the decision on hybrid tracking with OpenCV between turns, SAM at End Turn, SAM video for the replay
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0002]
sources: [docs/DeskTop_PRD.md#sam-usage-spec, docs/architecture/tracking-and-reanchor.md]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0002: Hybrid tracking with OpenCV between turns, SAM at End Turn, SAM video for the replay

Status: Accepted. Decided 2026-10-25 (PRD v0.2) by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-25 (PRD v0.2) |
| Owner | EHIBE |

## Context

SAM 3.1 takes images and uploaded clips, not a live stream. Each video request bills at least 50 frames. Per-frame SAM image calls at 5 FPS for 8 hours cost about $360, over the $150 credit. SAM has no multi-concept syntax.

## Decision

A local OpenCV KCF or CSRT tracker moves sprites between turns. One SAM image call with box prompts re-anchors every object at each End Turn. Muse Spark detects the new object and its box, then SAM box prompts give masks and stable app IDs 1 to 16. SAM video tracking runs only on the recorded replay proxy.

## Consequences

- Smooth sprites at zero cost between turns
- Exact positions at the moment that matters
- Drift reconcile ladder needed (see architecture/tracking-and-reanchor.md)
- Identity swaps of look-alike objects are a risk (R03)

## Alternatives considered

- Live 5 FPS SAM tracking (rejected: lag and cost)
- One SAM concept call for many objects (rejected: not supported)

## Sources

- `docs/DeskTop_PRD.md#sam-usage-spec`
- `docs/architecture/tracking-and-reanchor.md`
