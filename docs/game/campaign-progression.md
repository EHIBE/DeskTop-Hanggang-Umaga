---
title: Campaign progression
purpose: Barrio level, badges, scars and returning objects across nights (built 2026-11-04 as backend modules)
read_when: [touching campaign or next-night features after v1]
canonical_for: [progression rules, returning object match, recap, F16 scope]
sources: [docs/DeskTop_PRD.md#campaign-progression-could, docs/DeskTop_PRD.md#flow-f9-resume-next-night]
status: active
last_verified: 2026-11-04
related: [docs/product/scope-and-cuts.md, docs/architecture/data-model.md, docs/decisions/ADR-0113-post-freeze-cut-features.md]
---

# Campaign progression

Progression (F16) was cut by ADR-0112 and rebuilt by ADR-0113 on 2026-11-04. The rules, the returning object match and the recap exist as backend modules with offline tests. Wiring into the night loop and the screens is in progress. Autosave and Continue (F14) already existed.

## Key facts

| Fact | Value |
|---|---|
| Status | Built (offline tests, wiring in progress) |
| FRs | FR-42, FR-43, FR-56 |
| Modules | `backend/rules/progression.py`, `backend/vision/returning.py`, `backend/gm/recap.py`, `backend/gm/glimmer.py` |
| Storage | `campaign.barrio_level`, `campaign.nights_survived`, `unit.badges_json`, `unit.scars_json`, `unit.scars`, `campaign_recap` (schema v3) |
| Live checks | Manual: EHIBE (key, table, Ollama) |

## Rules (`rules/progression.py`)

| Rule | Value |
|---|---|
| Barrio level | `min(5, nights survived)`, never below 0 |
| Badge offer | After a survived night 1 to 5, each surviving unit gets the badges it can still take. A unit with no choice gets no offer |
| HP badge | +1 max HP. At most 2 per unit |
| Cooldown badge | -1 cooldown on its power through `cooldown_cut`. Not offered to the kubo or when the cooldown would reach 0 |
| Scar | A unit that went down loses 1 max HP with a floor of 1 and gains a scar. Applied by `apply_scars` |
| Errors | Applying an unavailable badge raises `ProgressionError` |
| Cap | The 12-object cap does not change |

## Returning object match (FR-42, `vision/returning.py`)

- Local only. No Spark call and no Muse Image call.
- Signature fields come from `vision/signature.py`: HSV histogram, footprint area in cm2, aspect ratio. The histograms are smoothed with a 3-tap kernel (0.25, 0.5, 0.25) before the Bhattacharyya compare.
- Score uses the signature weights (histogram, area, aspect). A candidate is dropped when histogram similarity is under 0.70.
- Match at a score of 0.78 or more, and only when the best beats the runner-up by 0.04 or more. Otherwise there is no match and the object is treated as new.
- Matched objects reuse the cached sprite and keep name, class, power, badges and scars. Line bank moment `object_recognized`. The older `welcome_back` copy key stays reserved.

## Recap (FR-43, `gm/recap.py`)

- Input is a `NightSummary`: night, outcome (sunrise or defeat), turns survived, enemies beaten, units downed, and units with badges and scars. Players are only P1 to P4, and any other label raises `RecapError`.
- Source order: local Muse Glimmer (`gm/glimmer.py`, only if configured and not offline), then Muse Spark (`night_recap` schema, skipped offline or in Demo Safe), then the line bank. Any failure or a 20 s timeout falls back to the line bank.
- `recap_tl` must start with "Kagabi". Text passes a number check against the summary, a P1 to P4 alias check and the content filter before it is used.
- The saved row in `campaign_recap` carries `source` (`spark`, `line_bank` or `glimmer`) so the screen can label it.
- Line bank moments: `recap_win`, `recap_lose`, `recap_badge`, `recap_scar`, `badge_earned`, `scar_gained`.

## Muse Glimmer (FR-53, `gm/glimmer.py`)

- A local Ollama style server at `DESKTOP_GLIMMER_URL`, `POST /api/chat`. Only `http` on `127.0.0.1`, `localhost` or `::1` is accepted. Anything else is ignored.
- Model name from `DESKTOP_GLIMMER_MODEL`, default `muse-glimmer`. Timeout 8 s. Cost 0, logged in `api_usage` with kind `glimmer`.
- Output uses the same schema checks and safety filter as Spark. It can also write one line of creature banter, which is rejected if it contains a digit.
- Unset means Glimmer is off and the chain starts at Spark.

## Data

Schema v3 adds `unit.scars_json` and the `campaign_recap` table. Canonical: `docs/architecture/data-model.md`.
