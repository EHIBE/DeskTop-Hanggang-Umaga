---
name: desktop-add-ws-message
description: "Add or change a WebSocket message between the DeskTop renderer and the FastAPI backend, with Pydantic and TypeScript types, the token and state checks, and the protocol doc updated. Use this whenever the renderer needs new data from the backend, a new button or tap sends an action, or the /ws handler or lib/socket.ts changes."
---

# Add a WebSocket message

The local socket is the only door into the backend. Anything that comes through it is untrusted, and both sides must agree on shapes, or the HUD silently breaks.

## Steps

1. Read `docs/architecture/websocket-protocol.md` and `docs/engineering/security-and-privacy.md`. Reuse an existing type if one fits.
2. Define the message with a `type` field. Add a Pydantic model with `extra="forbid"` in the backend and a matching type in `app/src/renderer/src/lib/types.ts`.
3. In the `/ws` handler, keep it thin: the connection is already token-checked with `hmac.compare_digest` and Origin-checked, then validate the message, check the current game state allows it, check every ID against live state, and delegate to `backend/game`.
4. Reply with validated fields only. Player-facing text goes as copy keys plus params.
5. Never put the API key or token in a message body.
6. Handle it in `lib/socket.ts` and the consuming component.
7. Add tests: valid message, unknown field rejected, wrong state rejected, unknown ID rejected, missing token rejected.
8. Move the type from Proposed to Established in `websocket-protocol.md`.
9. Run typecheck, lint and pytest and report the output.

## Done when

- Both sides typed, tests green, protocol doc updated.

## Always

- Follow `docs/FEATURE_PROMPT.md` sections 4, 5 and 9. Hard constraints win over this skill.
- Any agent you spawn runs on Sonnet 5.5 at medium effort (pass model sonnet).
- No code comments, no debug code, no new dependencies without EHIBE's approval.
- Doc prose has no semicolons and no em dashes.
- Finish with the `desktop-docs-sync` skill, then commit per `docs/engineering/git-and-commits.md` (EHIBE sole author, no trailers).
