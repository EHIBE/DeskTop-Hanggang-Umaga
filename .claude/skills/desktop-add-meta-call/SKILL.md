---
name: desktop-add-meta-call
description: "Add or change any call to a Meta model (Muse Spark, SAM 3.1, Muse Image, Muse Voice Transcribe, Files API) in DeskTop, with timeout, retries, circuit breaker, cost logging, strict schema, recorded fixture, offline test and local fallback. Use this whenever code will talk to api.meta.ai, a prompt or schema changes, or the user asks to 'use Spark for', 'call SAM', 'generate with Muse Image' or similar."
---

# Add a Meta model call

Every paid call can stall a turn, burn credits or return junk. DeskTop survives this because all calls share one client with the same guardrails and every call has a local fallback. A call outside that path breaks the budget and Demo Safe Mode.

## Steps

1. Read `docs/architecture/meta-api-integration.md`, `docs/architecture/ai-contracts.md`, `docs/architecture/reliability-and-fallbacks.md` and `docs/architecture/cost-and-budget.md`.
2. Add the call as a typed method on the client in `backend/meta_client.py`. Never create a second client.
3. Set the timeout from the documented table. Retries max 2 with 0.5 s and 1 s backoff, jitter up to 250 ms, honor Retry-After, no retry on HTTP 400.
4. Check the cost meter before the call ($90 warn, $120 hard stop) and log the call to `api_usage` with tokens, images, frames, audio seconds, Decimal cost, latency and ok.
5. For structured output, define a strict JSON schema (additionalProperties false, every property required, enums built from live IDs) and a mirroring Pydantic model in `backend/gm/schemas.py`.
6. Pass player text (names, transcripts, labels) as JSON data fields, never as instructions.
7. Validate, clamp and check IDs. One repair retry with the validation error, then the local fallback. Log failures as `gm_invalid`.
8. Define the fallback (line bank, local grammar, placeholder sprite, tracker position) with the same return shape, and wire it into Demo Safe Mode.
9. Record a fixture with one live smoke call, strip any key or header, save under `fixtures/`, and write an offline test that injects it.
10. Add the call row to `meta-api-integration.md` and its cost to `cost-and-budget.md`.

## Done when

- Offline test passes, fallback test passes, the call appears in api_usage in a manual run, and docs list it.

## Never

- Call Meta from the renderer, log the key or handshake, use Contributor mode, or call paid APIs in tests.

## Always

- Follow `docs/FEATURE_PROMPT.md` sections 4, 5 and 9. Hard constraints win over this skill.
- Any agent you spawn runs on Sonnet 5.5 at medium effort (pass model sonnet).
- No code comments, no debug code, no new dependencies without EHIBE's approval.
- Doc prose has no semicolons and no em dashes.
- Finish with the `desktop-docs-sync` skill, then commit per `docs/engineering/git-and-commits.md` (EHIBE sole author, no trailers).
