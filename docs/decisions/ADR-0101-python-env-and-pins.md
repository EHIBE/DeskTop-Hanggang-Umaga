---
title: ADR-0101 Rebuild backend venv and pin requirements
purpose: Record the decision on rebuild backend venv and pin requirements
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0101]
sources: [CLAUDE.md#bugs-and-contradictions, docs/FEATURE_PROMPT.md#3-project]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0101: Rebuild backend venv and pin requirements

Status: Proposed. Raised 2026-10-28. Awaiting EHIBE confirmation.

## Key facts

| Field | Value |
|---|---|
| Status | Proposed |
| Tracks | B1 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Needs EHIBE approval (dependency change). |

## Context

backend/requirements.txt is empty and backend/.venv does not exist. The PRD setup (section 12) and Build Guide 1.1 say the venv was created and pip freeze was run.

## Proposed decision

Recreate backend/.venv with py -3.11. Install the PRD package list (fastapi, uvicorn[standard], websockets, openai, opencv-contrib-python, numpy, pillow, shapely, pydantic, sounddevice, meta-sam-parser, python-dotenv, rapidfuzz, pytest). Freeze exact versions into requirements.txt. Consider adding mypy and ruff for strict analysis.

## Consequences

- Closes B1 once accepted and done
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/FEATURE_PROMPT.md#3-project`
