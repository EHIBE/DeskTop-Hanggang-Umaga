---
title: ADR-0101 Rebuild backend venv and pin requirements
purpose: Record the decision on rebuild backend venv and pin requirements
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0101]
sources: [CLAUDE.md#bugs-and-contradictions, docs/prompts/archive/FEATURE_PROMPT_docs_program.md#3-project]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0101: Rebuild backend venv and pin requirements

Status: Accepted. Raised 2026-10-28. Accepted 2026-10-28 by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Tracks | B1 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Approved 2026-10-28 with two amendments: Python 3.13 and OpenCV 4.x |

## Context

backend/requirements.txt is empty and backend/.venv does not exist. The PRD setup (section 12) and Build Guide 1.1 say the venv was created and pip freeze was run.

## Decision

Recreate backend/.venv with py -3.13, because Python 3.11 is not installed on the build laptop and every package publishes Python 3.13 builds (meta-sam-parser 0.1.0 declares Python 3.10 to 3.14). Install the PRD package list (fastapi, uvicorn[standard], websockets, openai, opencv-contrib-python, numpy, pillow, shapely, pydantic, sounddevice, meta-sam-parser, python-dotenv, rapidfuzz, pytest). Pin opencv-contrib-python to 4.14.0.94, the last 4.x release, because the KCF and CSRT tracker API in the docs targets 4.x. Add ruff, mypy and pytest-cov for strict analysis and the rules coverage target. Freeze exact versions into requirements.txt.

Python checks, run from `backend`:

- Lint: `.venv\Scripts\python -m ruff check .`
- Types: `.venv\Scripts\python -m mypy --strict --exclude .venv .`
- Coverage: `.venv\Scripts\python -m pytest tests -q --cov=rules`

pip-audit is not installed. Python dependency audit stays NONE configured.

## Consequences

- Closes B1. Done 2026-10-28, venv on Python 3.13.15, 48 pinned packages
- Docs that say `py -3.11` now mean the venv interpreter
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/prompts/archive/FEATURE_PROMPT_docs_program.md#3-project`
