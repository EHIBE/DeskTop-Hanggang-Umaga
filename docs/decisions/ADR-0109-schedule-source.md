---
title: ADR-0109 Build Guide schedule supersedes the PRD timeline
purpose: Record the decision on build Guide schedule supersedes the PRD timeline
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0109]
sources: [CLAUDE.md#bugs-and-contradictions, docs/prompts/archive/FEATURE_PROMPT_docs_program.md#3-project]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0109: Build Guide schedule supersedes the PRD timeline

Status: Accepted. Raised 2026-10-28. Accepted 2026-10-28 by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Tracks | B9 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Docs only. |

## Context

PRD section 17 freezes Nov 2 and submits Nov 4 8:00 PM SGT. The Build Guide, written Oct 27, moves the freeze to Nov 3 6:00 PM SGT and the target to Nov 4 11:00 PM SGT, and cuts F22, F12, Kapre smoke and every Could. Those cuts were later reversed: every cut feature was built after the freeze (superseded in part by ADR-0113).

## Decision

Treat the Build Guide schedule and cut list as current. docs/delivery/schedule.md is canonical.

## Consequences

- Closes B9 once accepted and done
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/prompts/archive/FEATURE_PROMPT_docs_program.md#3-project`
