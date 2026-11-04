---
title: ADR-0009 Record with ffmpeg to H.264 MP4
purpose: Record the decision on record with ffmpeg to H.264 MP4
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0009]
sources: [docs/DeskTop_PRD.md#flow-f8-replay, docs/architecture/sprite-pipeline.md]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0009: Record with ffmpeg to H.264 MP4

Status: Accepted. Decided 2026-10-25 (PRD section 12) by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-25 (PRD section 12) |
| Owner | EHIBE |

## Context

Browser MediaRecorder produces WebM. SAM 3.1 video accepts MP4 H.264 only.

## Decision

The backend pipes warped frames to ffmpeg (libx264, yuv420p, faststart) only after every player consents. The replay proxy is 10 FPS, 960 px wide.

## Consequences

- SAM video works on the recording
- ffmpeg must be on PATH
- Recording needs a consent gate (FR-44)

## Alternatives considered

- MediaRecorder WebM (rejected)

## Sources

- `docs/DeskTop_PRD.md#flow-f8-replay`
- `docs/architecture/sprite-pipeline.md`
