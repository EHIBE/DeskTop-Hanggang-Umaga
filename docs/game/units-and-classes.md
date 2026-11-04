---
title: Units and classes
purpose: How objects become units, the eight class templates, balance caps and the card clamp rule
read_when: [implementing backend/rules/units.py, summon, unit cards, writing unit tests]
canonical_for: [class templates, balance caps, clamp rule, roster limits, SAM ID slots for units]
sources: [docs/DeskTop_PRD.md#unit-system, docs/DeskTop_PRD.md#9-functional-requirements, docs/DeskTop_Build_Guide.md#43-rules-clamp]
status: active
last_verified: 2026-11-04
related: [docs/game/powers.md, docs/game/combat-math.md, docs/architecture/ai-contracts.md]
---

# Units and classes

Muse Spark picks one class and one power from fixed lists and writes flavor text. The rules engine owns every number and clamps whatever Spark returns.

## Key facts

| Fact | Value |
|---|---|
| Classes | kubo, charm, healer, fighter, reach, ranged, scout, wall |
| First summon | Always the kubo (FR-15), SAM ID 1 |
| Objects per night | 12 max (FR-16). SAM IDs 2 to 12 for other units, 13 to 16 reserved |
| Class caps | Max 2 Charms and 2 Walls per night. A third Charm or third Wall becomes fighter |
| Deltas | hp_delta and atk_delta each -1, 0 or +1, sum 0 or less |
| Floors and caps | HP floor 1, ATK floor 0, ATK cap 3 |
| Re-roll | 1 per unit |
| Module | `backend/rules/units.py` |

## Class templates

| Class | HP | ATK | Move | Range | Allowed powers | Example objects |
|---|---|---|---|---|---|---|
| Kubo (objective) | 10 | 0 | 0 | none | none | Mug, tumbler, box |
| Charm | 3 | 0 | 0 | none | P06, P07, P08, P12 | Coin, ring, bottle cap |
| Healer | 4 | 1 | Short (8 cm) | Melee (5 cm) | P01, P02 | Keys, lip balm, small bottle |
| Fighter | 6 | 2 | Medium (12 cm) | Melee (5 cm) | P03, P05, P11 | Stapler, phone, calculator |
| Reach | 4 | 2 | Medium (12 cm) | Reach (9 cm) | P04, P09 | Pen, pencil, ruler |
| Ranged | 3 | 1 | Medium (12 cm) | Far (15 cm) | P04, P10, P12 | Highlighter, earbuds case |
| Scout | 3 | 1 | Long (16 cm) | Melee (5 cm) | P11, P08 | Eraser, USB stick |
| Wall | 7 | 0 | Short (8 cm) | none | P02, P06 | Book, wallet, tape roll |

Kubo HP changes with difficulty: Madali 12, Normal 10, Mahirap 8 (`waves-and-difficulty.md`).

## Clamp rule (FR-10)

1. First summon becomes `kubo` whatever Spark says. Later summons that say `kubo` become `fighter`. A third Charm or third Wall also becomes `fighter` (`_resolve_class`).
2. If `hp_delta + atk_delta > 0`: when both are +1, set `atk_delta = -1`. When only `hp_delta` is +1, set it to 0. Otherwise set `atk_delta` to 0.
3. Power not in the class's allowed list becomes the class's first allowed power. Kubo power is `none`.
4. `hp = max(1, base_hp + hp_delta)`. `atk = min(3, max(0, base_atk + atk_delta))`.
5. Move and range come from the template only.

Acceptance example (FR-10): a card with hp_delta +1 and atk_delta +1 is clamped to atk_delta -1, so the sum is 0.

## Roster rules

| Rule | Message key |
|---|---|
| No kubo at Begin Night | `summon.kubo_first` |
| 13th object | `summon.full` (object ignored, excluded from prompts) |
| Exactly one kubo and at least 2 other units to begin | Begin Night disabled until valid. Fewer than 2 other units gives `summon.need_units` |
| Returning object (local signature match) | Keeps its stored sprite and unit. No re-roll and no sprite job (`game/night.py`) |
| Stacked objects (boxes overlap over 60%) | `summon.stack`, both Uncertain |
| Object placed mid-night | Ignored, small "?" outline, excluded from prompts |
| Profane name | Replaced by the class name (`design/cultural-care.md`) |

## Unit card fields

Name, class, HP, ATK, Galaw (Maikli, Katamtaman, Malayo), Abot (Lapit, Abot, Layo), power name and text in Taglish, English text, owner ("Wala pa" when none), badges and scars (marks only, `hud/UnitMarks.tsx`). Template: `design/copy-deck.md`. Example (illustrative): Albularyo ni Lola, Healer, HP 4, ATK 1, Gamot.

## Persistence

`unit` holds campaign-level identity and stats. `night_unit` holds per-night HP, position in cm, status, cooldown and the SAM slot. `unit.badges_json` and `unit.scars_json` hold earned badges and scars. `campaign.barrio_level` holds the barrio level. Numbers and rules: `game/campaign-progression.md`. Schema: `architecture/data-model.md`.
