---
title: ADR-0102 Wire Tailwind into the renderer
purpose: Record the decision on wire Tailwind into the renderer
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0102]
sources: [CLAUDE.md#bugs-and-contradictions, docs/prompts/archive/FEATURE_PROMPT_docs_program.md#3-project]
status: active
last_verified: 2026-10-28
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0102: Wire Tailwind into the renderer

Status: Accepted. Raised 2026-10-28. Accepted 2026-10-28 by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Tracks | B2 in CLAUDE.md |
| Raised | 2026-10-28 |
| Owner | EHIBE |
| Approval note | Moving packages is a dependency change and needs approval. Wiring the plugin does not. |

## Context

tailwindcss and @tailwindcss/vite are installed under dependencies, but electron.vite.config.ts has only react() in renderer plugins and main.css has no @import of tailwindcss. The Build Guide says install with -D.

## Decision

Add tailwindcss() to the renderer plugins and @import of tailwindcss at the top of main.css. Optionally move both packages to devDependencies.

## Consequences

- Closes B2 once accepted and done
- Update CLAUDE.md bugs table and this status when resolved

## Sources

- `CLAUDE.md#bugs-and-contradictions`
- `docs/prompts/archive/FEATURE_PROMPT_docs_program.md#3-project`
