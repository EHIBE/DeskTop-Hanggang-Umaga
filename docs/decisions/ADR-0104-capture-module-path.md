---
title: ADR-0104 Camera code lives in backend/capture/camera.py
purpose: Record the decision on camera code lives in backend/capture/camera.py
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0104]
sources: [CLAUDE.md#bugs-and-contradictions, docs/FEATURE_PROMPT.md#3-project]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0104: Camera code lives in backend/capture/camera.py

Status: Accepted. Raised 2026-10-28. Accepted 2026-10-28 by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Tracks | B4 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Docs only. |

## Context

Build Guide Phase 2 names backend/capture.py. The PRD tree and the scaffold use the package backend/capture/ with camera.py, calibration.py, tracker.py, recorder.py.

## Decision

Follow the PRD tree. Treat Build Guide paths as illustrative.

## Consequences

- Closes B4 once accepted and done
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/FEATURE_PROMPT.md#3-project`
