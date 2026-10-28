---
title: Win, lose and score
purpose: End conditions, score formula and the Bayani ng Gabi award
read_when: [implementing CHECK_END, sunrise or defeat screens, recap]
canonical_for: [win condition, lose condition, score formula, Bayani ng Gabi]
sources: [docs/DeskTop_PRD.md#win-and-lose, docs/DeskTop_PRD.md#flow-f7-sunrise]
status: active
last_verified: 2026-10-28
related: [docs/game/state-machine.md, docs/design/screens.md]
---

# Win, lose and score

The night is won if the kubo survives turn 8 resolution and lost the moment the kubo or every other unit falls. Score and the hero award show at sunrise and defeat.

## Key facts

| Result | Condition |
|---|---|
| Win | Kubo HP above 0 after turn 8 resolution |
| Lose | Kubo HP 0 at any time, or every non-kubo unit is down |
| Score | Units alive x 10 + kubo HP x 5 + enemies defeated x 3 |
| Bayani ng Gabi | Player credited with the most damage |

## Win sequence

1. Sky shifts to the dawn palette (#F4A6A0, #FFD9A0) over 3 s. Sprites lose the blue tint.
2. Enemies flee. Caption `win`: "Sumikat na ang araw! Ligtas ang baryo."
3. Score screen: units alive, kubo HP, enemies defeated, Bayani ng Gabi.
4. One recap line from Muse Spark (schema `recap`).
5. Replay button only if recording consent was given.
6. `night.result = win`, `night.recap_tl`, `night.recap_en` saved.

## Lose sequence

1. Fallen kubo art. Caption `lose`: "Nasira ang kubo... Subukan ulit bukas ng gabi."
2. Score and Try Again.
3. `night.result = lose`.

## Bayani ng Gabi credit

- Credit damage by speaker label when an order came by voice and the label maps to a player.
- Otherwise credit the unit owner.
- Ties: Unverified, no rule in the PRD. Proposed default: show all tied players.

## Worked score example (illustrative)

5 units alive, kubo HP 6, 9 enemies defeated: 5 x 10 + 6 x 5 + 9 x 3 = 50 + 30 + 27 = 107.
