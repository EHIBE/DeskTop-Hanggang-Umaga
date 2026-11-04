---
title: ADR-0008 Backend owns the camera and microphone
purpose: Record the decision on backend owns the camera and microphone
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0008]
sources: [docs/DeskTop_PRD.md#12-technical-architecture, docs/architecture/overview.md]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0008: Backend owns the camera and microphone

Status: Accepted. Decided 2026-10-25 (PRD section 12) by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-25 (PRD section 12) |
| Owner | EHIBE |

## Context

Windows often gives a webcam to one process at a time. Python needs the frames for tracking and recording.

## Decision

OpenCV in the backend opens the camera. sounddevice opens the mic. The renderer receives warped JPEG frames and poses over a local WebSocket.

## Consequences

- Renderer never touches devices
- One frame source for tracking, recording and display
- WebSocket bandwidth must be managed (JPEG quality 70, 960 px wide)

## Alternatives considered

- Renderer getUserMedia (rejected: device contention)

## Sources

- `docs/DeskTop_PRD.md#12-technical-architecture`
- `docs/architecture/overview.md`
