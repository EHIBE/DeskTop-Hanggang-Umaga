---
title: ADR-0007 Diarization plus enrollment with endpointing, push-to-talk and tap fallbacks
purpose: Record the decision on diarization plus enrollment with endpointing, push-to-talk and tap fallbacks
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0007]
sources: [docs/DeskTop_PRD.md#voice-spec, docs/architecture/voice-pipeline.md]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0007: Diarization plus enrollment with endpointing, push-to-talk and tap fallbacks

Status: Accepted. Decided 2026-10-25 (PRD v0.2) by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-25 (PRD v0.2) |
| Owner | EHIBE |

## Context

Diarization is not tuned for low-latency commands and speaker labels are session-scoped. Keywords are fixed at session start.

## Decision

Run two voice sessions per night: summon in ENDPOINTING mode, night in DIARIZATION mode with keywords for unit, player and creature names. Map labels to players through a spoken claim (Ako si ...). Ownership is soft, so any voice can command any unit. Fall back to ENDPOINTING, then push-to-talk (hold Space), then tap controls.

## Consequences

- Play works even when labels are wrong
- Re-claim needed each night and after a 60 min session
- Strict ownership is a Could (FR-55)

## Alternatives considered

- Diarization as the only command path (rejected)

## Sources

- `docs/DeskTop_PRD.md#voice-spec`
- `docs/architecture/voice-pipeline.md`
