---
title: Campaign progression
purpose: Barrio level, badges, scars and returning objects across nights (Could, not scheduled)
read_when: [touching campaign or next-night features after v1]
canonical_for: [progression rules, F16 scope]
sources: [docs/DeskTop_PRD.md#campaign-progression-could, docs/DeskTop_PRD.md#flow-f9-resume-next-night]
status: active
last_verified: 2026-11-03
related: [docs/product/scope-and-cuts.md, docs/architecture/data-model.md]
---

# Campaign progression

Progression (F16) is cut by ADR-0112 and is not built. Autosave and Continue still exist (F14), so a campaign can resume, but badges, scars, recaps and object recognition wait.

## Key facts

| Fact | Value |
|---|---|
| Status | Could, not scheduled |
| FRs | FR-42, FR-43, FR-56 |
| Still in v1 | Campaign rows, autosave, Continue, sprite cache reuse (FR-13) |

## Rules (for when it ships)

| Rule | Value |
|---|---|
| Barrio level | +1 per night survived, max 5 |
| Per level | One badge per surviving unit. The 12-object cap does not change |
| Badge options | +1 max HP or -1 cooldown on its power. Chosen by tap at sunrise |
| Scar | A unit that went down starts next night with -1 max HP (floor 1) and a scar mark |
| Recognition | Returning objects keep name, class, power, badges, scars and sprite |

## Returning object match (FR-42)

- Signature: label, HSV histogram (8x4x4 bins over the masked crop), footprint area in cm2, aspect ratio, 128 px reference crop.
- Score = 0.5 histogram + 0.3 area + 0.2 aspect. Match at 0.8 or more.
- Ties within 0.05 go to Spark with up to 6 stored crops (effort low).
- Matched objects reuse the cached sprite with no Muse Image call. Message `welcome_back`.

## Recap (FR-43)

"Kagabi..." uses `night.recap_tl` and `recap_en` from the previous night. Glimmer may write it (FR-53, Could) and must be labeled.

## Data already in the schema

`campaign.barrio_level`, `campaign.nights_survived`, `unit.badges_json`, `unit.scars`, `object_signature`. Keep these columns so v1 data stays forward compatible.
