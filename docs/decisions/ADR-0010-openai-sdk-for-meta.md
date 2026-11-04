---
title: ADR-0010 OpenAI Python SDK for Meta Responses and Files, websockets for voice, meta-sam-parser for SAM
purpose: Record the decision on openAI Python SDK for Meta Responses and Files, websockets for voice, meta-sam-parser for SAM
read_when: [changing this area, questioning this choice]
canonical_for: [ADR-0010]
sources: [docs/DeskTop_PRD.md#per-model-integration-table, docs/architecture/meta-api-integration.md]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, CLAUDE.md]
---

# ADR-0010: OpenAI Python SDK for Meta Responses and Files, websockets for voice, meta-sam-parser for SAM

Status: Accepted. Decided 2026-10-25 (PRD section 12) by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-25 (PRD section 12) |
| Owner | EHIBE |

## Context

Meta docs confirm OpenAI SDK compatibility. SAM output uses a token grammar with confidence fields.

## Decision

Use the OpenAI SDK with base_url https://api.meta.ai/v1 for Responses and Files. Use the websockets library for realtime voice. Use meta-sam-parser 0.0.6 or later to build prompts and parse SAM output. All calls go through backend/meta_client.py.

## Consequences

- API key never reaches the renderer
- Structured output field layout must be verified (A6)
- Chat Completions response_format is the fallback

## Alternatives considered

- Hand-written HTTP client (rejected: more code)
- Hand-parsing SAM grammar (rejected: error prone)

## Sources

- `docs/DeskTop_PRD.md#per-model-integration-table`
- `docs/architecture/meta-api-integration.md`
