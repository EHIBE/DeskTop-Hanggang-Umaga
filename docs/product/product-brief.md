---
title: Product brief
purpose: One-page summary of what DeskTop is, why it exists and how it uses Meta models
read_when: [onboarding, writing pitch or README text, explaining the product]
canonical_for: [elevator pitch, model map summary]
sources: [docs/DeskTop_PRD.md#1-summary-one-pager, docs/DeskTop_PRD.md#2-working-backwards-press-release-and-faq]
status: active
last_verified: 2026-10-28
related: [docs/product/goals-and-metrics.md, docs/market/positioning-and-messaging.md, docs/architecture/meta-api-integration.md]
---

# Product brief

DeskTop: Hanggang Umaga turns everyday objects on a real desk into pixel art units in a turn-based co-op game against Filipino folklore creatures. It needs only a laptop, a webcam pointed at the desk, and one A4 sheet.

## Key facts

| Fact | Value |
|---|---|
| Name | DeskTop: Hanggang Umaga |
| Tagline | DeskTop: any desk is a game board. |
| Version | PRD v1.1, approved for build |
| Owner | EHIBE (solo builder, PM, design, engineering), General Santos City |
| Event | Meta Global AI Developer Hackathon 2026, Indie track, Build for Your World |
| Players | 1 to 4, co-op, one table |
| Session | About 3 min setup plus 12 to 18 min night (8 turns) |
| Hardware | Windows laptop, top-down webcam 45 to 70 cm above desk, one A4 sheet |
| Cost per night | About $0.49 expected, about $1.40 worst case (estimate) |
| Repo | github.com/EHIBE/DeskTop-Hanggang-Umaga |

## One-pager

| | |
|---|---|
| Problem | Friends at the same table play on separate screens. Tabletop games cost money, take space and are mostly in English. Nothing turns what is already on the table into a shared game |
| Solution | Everyday objects become pixel art units. Players move real objects by hand and give orders out loud in Taglish. An AI Game Master runs the night. Folklore creatures attack until sunrise |
| For whom | Barkadas, student orgs and classrooms, families, Filipino diaspora. First market: the Philippines |
| Success | Full 8-turn night on camera with no crash. Registration correct 9 of 10. Voice to on-screen text in 3 s or less. Cost per night under $1 |
| In scope | Calibration, summon, voice claim, 8-turn night, 5 enemy types, deterministic rules, GM narration, autosave, replay reel, Demo Safe Mode |
| Out of scope | Real-time action, online multiplayer, mobile, cloud hosting, accounts, PvP, monetization |
| Top risks | Schedule overload (R01), look-alike identity swaps (R03), diarization in noisy rooms (R04) |

## How a night plays

1. Calibrate with an A4 sheet. The desk becomes a top-down board.
2. Summon. Place one object, say what it is. The first is always the bahay kubo.
3. Voice claim. Each player says "Ako si [name], hawak ko ang [units]."
4. Eight turns. Enemies spawn and telegraph. Players talk, slide objects, give orders, say "Tapos".
5. Sunrise or defeat. Score, Bayani ng Gabi, then a replay reel of real hands with the pixel battle on top.

## Model map

Summary. Canonical: `docs/architecture/meta-api-integration.md`.

| Model | Job |
|---|---|
| Muse Spark 1.3 | Finds and names the new object, writes its unit card, narrates each turn, parses free-form orders, writes the recap |
| SAM 3.1 | Exact mask and stable ID per object, End Turn re-anchor, video tracking for the replay |
| Muse Image 1.0 | Redraws each object as a 16-bit sprite in one shared style |
| Muse Voice Transcribe 1.0 | Taglish with code-switching, speaker labels, turn detection |
| OpenCV (local) | Moves sprites between turns. No cost |
| Rules engine (local) | Decides every number |

## Why standard chat AI cannot do this

- A chat model gives approximate boxes, not pixel masks with stable IDs across video. SAM 3.1 does.
- A chat model cannot redraw an object as a sprite that matches a shared style. Muse Image edits from a reference.
- A chat model cannot listen to a room, split speakers and follow Taglish live. Muse Voice Transcribe does.
- A chat window has no game state, rules or physical board. DeskTop joins four models to a rules engine and a real desk.

## Press release headline

"DeskTop turns any desk into a Filipino folklore battlefield." Full text and FAQ: PRD section 2. The player quote there is fictional and the builder quote is a draft for EHIBE to approve.

## FAQ highlights

| Question | Answer |
|---|---|
| Do I have to speak Tagalog? | No. English, Tagalog and Taglish work. Every voice action has a tap button |
| What objects work? | Coin size to mug size. Up to 12 per night |
| Is my video uploaded? | No. Single frames and crops go to Meta, mic audio is streamed. The replay sends a short low-res clip only with consent, deleted within 24 hours |
| Is it scary? | Spooky, not gory. General audience. Cute 16-bit style |
| What if a model fails live? | Demo Safe Mode keeps the night playing |
