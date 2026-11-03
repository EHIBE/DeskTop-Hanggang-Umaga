---
title: ADR-0113 Post-freeze cut features
purpose: Record EHIBE's decision to build every cut feature before the zip, the trade-off and each feature's default
read_when: [questioning a post-freeze feature, changing a default, planning playtests or the video, changing powers]
canonical_for: [ADR-0113, post-freeze feature defaults]
sources: [docs/decisions/ADR-0112-finalization-scope.md, docs/product/scope-and-cuts.md, docs/FINALIZATION_PLAN.md]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, docs/decisions/ADR-0112-finalization-scope.md, docs/game/campaign-progression.md, docs/game/enemies.md, docs/game/powers.md]
---

# ADR-0113: Post-freeze cut features

Status: Accepted. Decided 2026-11-03 at 11:45 PM SGT by EHIBE.

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-11-03, 11:45 PM SGT |
| Owner | EHIBE |
| Decision | Build every cut feature before the packaged zip |
| Supersedes in part | ADR-0112 (cuts of the Settings screen and F16, and the removal of P08 from Charm and Scout) |
| Built | Backend modules with offline tests, committed 2026-11-04. Wiring into the night loop and the screens is in progress |
| Not built | A Tagalog TTS engine. `tts_enabled` exists and stays off |

## Context

The feature freeze passed on 2026-11-03 at 6:00 PM SGT with these features cut: Kapre smoke, Lost detection (F22), the Spark fallback parser (F12), progression with returning objects and recap (F16), Glimmer recap (F19), generated map (F20), strict ownership (F21) and the Settings screen (F23). EHIBE chose to build all of them before the zip. Each was already specified in the PRD and earlier docs.

## Decision

Build the features below. Each one has a default that keeps the earlier behavior, so a feature that is not wired or not configured costs nothing at the table.

| Feature | FR | Module | Default |
|---|---|---|---|
| Kapre smoke | FR-36 | `rules/resolve.py` | On. Smoke on the Kapre's 2nd and 4th turn alive, a 10 cm cloud. A unit inside a cloud cannot hit an enemy outside every cloud |
| P08 Liwanag | FR-36 | `rules/units.py`, `rules/resolve.py` | Back on Charm (P06, P07, P08, P12) and Scout (P11, P08). Clears clouds within 12 cm before attacks |
| Lost detection | FR-30 | `rules/lost.py` | On. `off_desk` is set when the centroid is outside the play area at the End Turn snapshot |
| Progression | FR-56 | `rules/progression.py` | On. Barrio level is `min(5, nights survived)`. HP badge +1 max HP, at most 2. Cooldown badge -1. A scar costs 1 max HP, floor 1 |
| Returning objects | FR-42 | `vision/returning.py` | On. Local signature match, threshold 0.78, ambiguity margin 0.04 |
| Kagabi recap | FR-43 | `gm/recap.py` | On. Glimmer, then Spark, then the line bank. Line bank when offline |
| Spark fallback parser | FR-21 | `voice/fallback.py` | On when Spark is available. Effort minimal, enum schema. Skipped offline and in Demo Safe |
| Strict ownership | FR-55 | `voice/ownership.py` | Off (`strict_ownership` is false) |
| Generated barrio map | FR-54 | `vision/barrio_map.py` | Off (`generated_map` is false). $0.01 per campaign, cached |
| Muse Glimmer recap | FR-53 | `gm/glimmer.py` | Off until `DESKTOP_GLIMMER_URL` is set. Loopback only, cost 0 |
| Settings storage | FR-49 | `db/store.py` | Defaults match earlier behavior. The screen is in progress |

Schema moves to version 3 with additive changes only: `campaign.map_image_path`, `unit.scars_json` and the `campaign_recap` table. The nine preference keys live in the existing `settings` table. Canonical: `docs/architecture/data-model.md`.

The grammar fuzzy match now needs a window of at least 4 characters. This fixed "pre" matching "spear".

## Consequences

- Less time for Playtest 1, Playtest 2, the table run and the video. The finalization plan's hours for them shrink by the build time
- Every feature needs a live check that needs the key, the camera or Ollama. Those checks are Manual: EHIBE and stay open
- Rules numbers still come from the rules engine. Models only choose from enums or narrate
- Wiring in progress means a feature can be tested offline and still be absent from a screen. Requirement statuses say so
- One extra Muse Image call per campaign only when the map setting is on. The $90 warn and $120 stop do not change
- Glimmer needs a local Ollama server. Without it the recap uses Spark or the line bank
- The finalization cut order in `docs/product/scope-and-cuts.md` still applies if time runs out. Turning a feature's default off is the first fallback

## Alternatives considered

- Keep the cuts and spend the hours on playtests and the video (rejected by EHIBE)
- Build only the Should features, F22 and F12 (rejected by EHIBE, every cut feature is built)
- Ship the Could features on by default (rejected: strict ownership, the map and Glimmer change table behavior or cost, so they stay off)

## Sources

- `docs/decisions/ADR-0112-finalization-scope.md`
- `docs/product/scope-and-cuts.md`
- `docs/game/campaign-progression.md`
