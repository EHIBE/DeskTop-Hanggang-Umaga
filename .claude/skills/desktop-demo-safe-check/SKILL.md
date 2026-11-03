---
name: desktop-demo-safe-check
description: "Verify that a DeskTop feature still works, or degrades correctly, when the network is off, a Meta model fails, credits hit the hard stop, or Demo Safe Mode is on. Use this before marking any feature done that calls a model, before demo recording or live finals, and whenever the user mentions offline, fallback, outage, Demo Safe Mode or 'what if the API breaks'."
---

# Demo Safe check

The live demo and the recorded video are worth half the judging score, and the network will fail at the worst time. Demo Safe Mode is the promise that the night still finishes. This skill checks that promise for one feature or the whole build.

## Steps

1. Read `docs/architecture/reliability-and-fallbacks.md` and `docs/delivery/demo-runbook.md`.
2. For the feature, list each external call and its documented fallback.
3. Check in code that each fallback exists, returns the same shape, and is switched on by `backend/game/demo_safe.py`.
4. Check tests cover the timeout path, the breaker-open path and the hard-stop path with fixtures.
5. Manual check with the `run` skill: start the app with Wi-Fi off and Demo Safe Mode on, play through the affected phase, and confirm no blocking spinner, no raw error, and the right copy-deck banner.
6. Check cached sprites and cards exist for the demo object set (mug, coin, keys, pen, eraser).
7. Record the result in `docs/delivery/demo-runbook.md` or `docs/playtests.md` with the date.

## Done when

- Every call in scope has a tested fallback, and a Wi-Fi-off run of the phase completes.

## Delegate

`desktop-demo-readiness-checker` for a read-only whole-build review.

## Always

- Follow `docs/prompts/FEATURE_PROMPT.md` sections 4, 5 and 9. Hard constraints win over this skill.
- Any agent you spawn runs on Sonnet 5.5 at medium effort (pass model sonnet).
- No code comments, no debug code, no new dependencies without EHIBE's approval.
- Doc prose has no semicolons and no em dashes.
- Finish with the `desktop-docs-sync` skill, then commit per `docs/engineering/git-and-commits.md` (EHIBE sole author, no trailers).
