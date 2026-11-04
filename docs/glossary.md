---
title: Glossary
purpose: Single table of Filipino, game, technical terms and ID prefixes used across the project
read_when: [meeting an unfamiliar term, naming things in code or copy]
canonical_for: [term definitions, ID prefixes]
sources: [docs/DeskTop_PRD.md#22-appendix, docs/DeskTop_PRD.md#content-list]
status: active
last_verified: 2026-11-04
related: [docs/design/cultural-care.md, docs/design/copy-deck.md]
---

# Glossary

Every term the project uses, in one place. In-app folklore descriptions are canonical in `design/cultural-care.md`, this file gives short meanings.

## Key facts

| Fact | Value |
|---|---|
| Languages | English, Tagalog, Taglish (code-switched) |
| ID prefixes | See "ID prefixes" below |

## Filipino terms

| Term | Meaning |
|---|---|
| Albularyo | Traditional folk healer |
| Anting-anting | Protective amulet |
| Asin | Salt (power P12) |
| Aswang | Shape-shifting night creature |
| Bahay kubo | Traditional bamboo and nipa house. The objective unit |
| Barkada | Close group of friends |
| Baryo | Village (barrio) |
| Bayani ng Gabi | Hero of the Night. Sunrise award |
| Duwende | Small mound-dwelling spirit, lucky or mischievous |
| Gabi | Night. Also the palette name Gabi 16 |
| Gubat | Forest |
| Hanggang umaga | Until morning |
| Hindi | No. Voice cancel word |
| Ibalik mo | Put it back |
| Isa-isa lang | One at a time |
| Kagabi | Last night |
| Kakampi | Ally |
| Kalaban | Enemy |
| Kapre | Tree-dwelling giant who smokes a big cigar |
| Madali / Normal / Mahirap | Easy / Normal / Hard |
| Manananggal | Creature that splits its upper body from its lower half and flies |
| Nakaiwas | Dodged |
| Payag | Agree. Recording consent button |
| Piyesa | Piece |
| Punso | Mound where duwende live |
| Saksakin | Stab |
| Gamutin | Heal |
| Protektahan | Protect |
| Tabi tabi po | Polite phrase asking spirits for permission to pass. Gives a small bonus |
| Taglish | Tagalog mixed with English in one sentence |
| Tapos / Tapos na | Done. Voice End Turn word |
| Tikbalang | Tall horse-headed creature that leads travelers astray |

## Game terms

| Term | Meaning |
|---|---|
| Night | One game session of 8 turns |
| Turn | Spawn and telegraph, player phase, End Turn, resolution, enemy attack, effects, check |
| Kubo | The objective unit. Exactly one per night, always the first summon, SAM ID 1 |
| Summon | Registering a real object as a unit |
| Unit card | Name, class, stats, power, Taglish and English text |
| Telegraph | Red intent arrow showing which unit an enemy will attack and for how much |
| Intent | A confirmed player order: unit, action, target |
| Order chip | On-screen chip for an intent before it resolves |
| Re-anchor | SAM image call at End Turn that sets exact positions |
| Ghost | Outline showing a start position or a push target |
| Lost | Unit off the play area. Cannot act or be targeted |
| Stolen | Unit taken by a duwende |
| Scar | -1 max HP for a unit that went down, floor 1 (`rules/progression.py`) |
| Peklat | Filipino label for a scar (`scar.label` in `copy.ts`) |
| Usok ng Kapre | Smoke cloud from a kapre. 10 cm radius, hides what is inside (`SMOKE_RADIUS_CM` in `rules/resolve.py`) |
| Liwanag | Power P08. Clears smoke clouds within 12 cm (`SMOKE_CLEAR_RADIUS_CM`) |
| Badge | Reward a unit picks after a night. Either +1 max HP (at most 2 of these) or Cooldown -1 (`rules/progression.py`) |
| Barrio level | `min(5, nights survived)`. Stored as `campaign.barrio_level` |
| Returning object | Object from an earlier night matched by local signature. Keeps its unit and sprite (`vision/returning.py`) |
| Demo Safe Mode | Offline-capable mode with cached assets, local narration, local grammar, tap controls |
| Forest edge | Outer 5 cm of the play area where enemies spawn |
| Line bank | Local fallback narration lines in `assets/lines.json` |

## Technical terms

| Term | Meaning |
|---|---|
| Homography | Perspective transform from camera view to top-down desk plane |
| Warped frame | Top-down camera frame after homography |
| px per cm | Scale of the warped frame. 20 in the Build Guide |
| Box prompt | SAM input giving an object ID and a bounding box |
| Concept prompt | SAM input with a noun label, one concept per request |
| Diarization | Voice mode that labels speakers A, B, C, D |
| Endpointing | Voice mode that detects end of speech for single commands |
| Chroma key | Removing the #FF00FF or #00FF00 background from a sprite |
| Style anchor | First accepted sprite of a campaign, reused as a style reference |
| Circuit breaker | 3 consecutive failures on one model opens its fallback for 2 minutes |
| Fixture | Recorded API response used by offline tests |
| Signature | Object fingerprint: label, HSV histogram, area, aspect, reference crop |

## ID prefixes

| Prefix | Meaning | Canonical list |
|---|---|---|
| FR-01 to FR-56 | Functional requirements | `product/requirements-index.md` |
| NFR-01 to NFR-31 | Non-functional requirements | `product/requirements-index.md` |
| F01 to F24 | Feature groups (RICE) | `product/requirements-index.md` |
| JS-01 to JS-14 | Job stories | `product/personas-and-jobs.md` |
| PG-1 to PG-5 | Product goals | `product/goals-and-metrics.md` |
| P01 to P12 | Powers | `game/powers.md` |
| R01 to R19 | Risks | `delivery/risk-register.md` |
| E1 to E7 | Evals | `engineering/testing-strategy.md` |
| A1 to A16, Q1 to Q9 | Assumptions, open questions | `product/open-questions.md` |
| ADR-0001+ | Decisions | `decisions/README.md` |
| B1+ | Known bugs and contradictions | `CLAUDE.md` |
| u_* | Unit IDs in game state | `architecture/data-model.md` |
| e_<type>_<n> | Enemy IDs in game state | `architecture/data-model.md` |
| SAM IDs 1 to 16 | Per-night object slots. 1 kubo, 2 to 12 units, 13 to 16 reserved | `architecture/meta-api-integration.md` |
| Copy keys (calib.place) | Player-facing text keys | `design/copy-deck.md` |
