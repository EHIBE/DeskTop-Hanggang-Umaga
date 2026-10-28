---
name: desktop-add-power-or-enemy
description: "Add or change a power (P01 to P12), an enemy type, an enemy AI rule, a wave, or a difficulty rule in DeskTop: Hanggang Umaga, with rules code, tests, docs and line bank entries kept in sync. Use this whenever the task touches backend/rules, balance numbers, enemy behavior, spawns, cooldowns or class power lists, even if the user only says 'make the aswang faster' or 'add a new creature'."
---

# Add or change a power, enemy or wave

The rules engine is the only source of numbers in DeskTop, and judges rely on it being deterministic. A change here must land in code, tests and docs together, or the GM, HUD and docs will disagree about what happened.

## Steps

1. Read `docs/game/combat-math.md`, `docs/game/powers.md`, `docs/game/enemies.md`, `docs/game/waves-and-difficulty.md` and `docs/game/balance-and-tuning.md`.
2. State the change as testable checks (inputs, expected events, expected numbers).
3. Edit only `backend/rules/` (units.py for powers and class lists, enemies.py for stats and AI, waves.py for spawns and scaling, resolve.py for resolution). Keep functions pure: no I/O, no clock, no randomness.
4. Put new constants in `backend/config.py` or a named module constant.
5. Add tests in `backend/tests/` for the happy path, range edges with the +1 cm tolerance, cooldowns, and a determinism check (same state and intents twice give identical events).
6. If the change adds an event type, add it to the event schema in `docs/architecture/websocket-protocol.md` and the GM input list in `docs/architecture/ai-contracts.md`.
7. If players will see it, add line bank or copy entries with the `desktop-add-copy-key` skill, and enemy art notes to `docs/design/art-direction.md`.
8. Update the canonical game doc table and log the change in the tuning log of `balance-and-tuning.md`.
9. Run `backend\.venv\Scripts\python -m pytest backend/tests -q` and report the real output.

## Done when

- Tests green, E7 determinism still 100%, resolution still under 50 ms.
- Game docs, tuning log and requirements-index status match the code.

## Delegate

`desktop-rules-engineer` for the code and tests. `desktop-cultural-reviewer` for any new creature or folklore text.

## Always

- Follow `docs/FEATURE_PROMPT.md` sections 4, 5 and 9. Hard constraints win over this skill.
- Any agent you spawn runs on Sonnet 5.5 at medium effort (pass model sonnet).
- No code comments, no debug code, no new dependencies without EHIBE's approval.
- Doc prose has no semicolons and no em dashes.
- Finish with the `desktop-docs-sync` skill, then commit per `docs/engineering/git-and-commits.md` (EHIBE sole author, no trailers).
