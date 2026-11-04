---
title: Decision records index
purpose: List every architecture decision record and how to add one
read_when: [making or questioning a design choice, resolving a contradiction]
canonical_for: [ADR index, ADR process]
sources: [docs/DeskTop_PRD.md#0-document-header, CLAUDE.md#bugs-and-contradictions]
status: active
last_verified: 2026-11-04
related: [docs/decisions/TEMPLATE.md, CLAUDE.md]
---

# Decision records

Each record explains one decision: its context, the choice, and the cost. Accepted records are binding. Proposed records wait for EHIBE.

## Key facts

| Fact | Value |
|---|---|
| Accepted | ADR-0001 to ADR-0012, ADR-0101 to ADR-0113 |
| Proposed | None |
| Numbering | 0001+ for decisions, 0101+ for contradiction fixes |
| Template | `TEMPLATE.md` |

## Accepted

| ADR | Decision | Date |
|---|---|---|
| [0001](ADR-0001-turn-based-co-op.md) | Turn-based co-op survival over real-time RPG | 2026-10-25 |
| [0002](ADR-0002-hybrid-tracking.md) | Hybrid tracking, SAM at End Turn, SAM video for replay | 2026-10-25 |
| [0003](ADR-0003-deterministic-rules-engine.md) | Deterministic rules engine is authoritative | 2026-10-25 |
| [0004](ADR-0004-sqlite-state.md) | SQLite for state, Glimmer only as a Could | 2026-10-25 |
| [0005](ADR-0005-chroma-key-sprites.md) | Key color background plus local chroma key | 2026-10-25 |
| [0006](ADR-0006-local-first.md) | Local-first, no cloud hosting | 2026-10-25 |
| [0007](ADR-0007-voice-diarization-enrollment.md) | Diarization plus enrollment with fallbacks | 2026-10-25 |
| [0008](ADR-0008-backend-owns-devices.md) | Backend owns camera and mic | 2026-10-25 |
| [0009](ADR-0009-ffmpeg-h264-recording.md) | ffmpeg H.264 MP4 recording | 2026-10-25 |
| [0010](ADR-0010-openai-sdk-for-meta.md) | OpenAI SDK for Meta, websockets for voice, meta-sam-parser | 2026-10-25 |
| [0011](ADR-0011-agents-sonnet-medium.md) | All agents on Sonnet 5.5 at medium effort | 2026-10-28 |
| [0012](ADR-0012-mvp-build-defaults.md) | MVP build defaults for open rules, content and runtime gaps | 2026-10-28 |
| [0101](ADR-0101-python-env-and-pins.md) | Rebuild backend venv and pin requirements (B1) | 2026-10-28 |
| [0102](ADR-0102-wire-tailwind.md) | Wire Tailwind into the renderer (B2) | 2026-10-28 |
| [0103](ADR-0103-electron-hardening.md) | Harden Electron window and preload (B3) | 2026-10-28 |
| [0104](ADR-0104-capture-module-path.md) | Camera code in backend/capture/camera.py (B4) | 2026-10-28 |
| [0105](ADR-0105-warped-frame-size.md) | Warped frame 1200x800 at 20 px per cm (B5) | 2026-10-28 |
| [0106](ADR-0106-token-compare-and-client-injection.md) | Constant-time token compare, injected client (B6) | 2026-10-28 |
| [0107](ADR-0107-money-precision.md) | Decimal for cost math (B7) | 2026-10-28 |
| [0108](ADR-0108-scaffold-placeholders.md) | Replace scaffold placeholders (B8) | 2026-10-28 |
| [0109](ADR-0109-schedule-source.md) | Build Guide schedule supersedes PRD timeline (B9) | 2026-10-28 |
| [0110](ADR-0110-missing-prd-prompt.md) | Missing DeskTop_PRD_Prompt.md (B10) | 2026-10-28 |
| [0111](ADR-0111-packaged-build-and-origin.md) | Packaged zip, fuses through electron-builder, `null` origin only when packaged | 2026-11-03 |
| [0112](ADR-0112-finalization-scope.md) | Finalization scope: game feel features, cuts, no pip-audit. The Settings and F16 cuts and P08 off Charm and Scout are superseded by ADR-0113 | 2026-11-03 |
| [0113](ADR-0113-post-freeze-cut-features.md) | Post-freeze cut features: build every cut feature before the zip, each off or fallback by default | 2026-11-03 |

## Proposed

None.

## Earlier decisions in the PRD change log

The PRD change log (section 0) records the history these ADRs summarize: rename to DeskTop (v0.1), hybrid tracking, Spark plus SAM box prompts, key color sprites, diarization plus enrollment, SQLite, no cloud (v0.2), turn-based Hanggang Umaga (v0.3), authoritative rules engine, telegraphing, Demo Safe Mode (v1.0), setup and folder structure (v1.1).

## How to add a decision

1. Copy `TEMPLATE.md` to `ADR-<next number>-<slug>.md`.
2. Fill context, decision, consequences, alternatives, sources.
3. Status Proposed until EHIBE confirms, with front matter `status: draft`. Then Accepted with `status: active`.
4. Superseding a decision: set the old one to Superseded and link the new one.
5. Add a row to this index and update CLAUDE.md Decisions.
