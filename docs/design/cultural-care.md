---
title: Cultural care
purpose: Rules and review checklist for folklore, Taglish, names and generated content
read_when: [writing copy or prompts, making enemy art, reviewing GM output, before recording]
canonical_for: [in-app folklore glossary, cultural rules, content safety controls, review checklist]
sources: [docs/DeskTop_PRD.md#cultural-care, docs/DeskTop_PRD.md#content-list, docs/DeskTop_PRD.md#content-safety]
status: active
last_verified: 2026-11-04
related: [docs/design/copy-deck.md, docs/architecture/ai-contracts.md, docs/game/enemies.md]
---

# Cultural care

DeskTop uses creatures and words that real Filipino communities live with. The game shows them with respect, without gore, and never ties a monster to a real place.

## Key facts

| Rule | Value |
|---|---|
| Rating | General audience. Spooky, not gory |
| Place names | Never name a real town, province or community as home of a monster |
| Review | At least 2 Filipino playtesters review Taglish lines before recording |
| Name filter | Local English and Tagalog profanity list on all player names and generated text |
| Reviewer agent | `desktop-cultural-reviewer` (Sonnet, medium effort) |

## Why the place-name rule exists

Some places in the Philippines face real stigma from aswang stories. Creatures follow common, widely told versions of each story with no regional home.

## In-app folklore glossary

| Term | In-app description |
|---|---|
| Aswang | A shape-shifting night creature in Philippine folklore that hunts people who wander alone |
| Tikbalang | A tall creature with a horse's head that leads travelers astray in forests and mountains |
| Kapre | A big tree giant that sits in large trees like the balete and smokes a huge cigar |
| Manananggal | A creature that splits its upper body from its lower half and flies at night. Salt on the lower half stops it from rejoining |
| Duwende | A small spirit that lives in mounds (punso) and can bring luck or mischief. People say "tabi tabi po" to ask permission to pass |
| Albularyo | A traditional folk healer |
| Anting-anting | An amulet believed to give protection |
| Bahay kubo | A traditional Filipino house made of bamboo and nipa |
| Usok ng Kapre | The smoke of the kapre's big cigar. It hides whatever stands inside until a light clears it |
| Liwanag | A power of light that clears the kapre's smoke around a piece |

The in-app glossary has 10 entries (`components/GlossaryPanel.tsx`, `gloss.*` keys in `lib/copy.ts`). Text above is the ENG text.

Open item: the `tl` text of the eight older entries (Aswang to Bahay kubo) in `copy.ts` is still English. Only Usok ng Kapre and Liwanag have real Tagalog. Needs a Filipino reviewer.

## Rules

- No gore, blood splatter or body horror. Defeated creatures puff into smoke.
- No slurs, no real people, no politics, no religion mocked.
- Albularyo and anting-anting are shown with respect.
- Player-entered names pass the profanity filter. Blocked names become the class name.

## Content safety controls

| Risk | Control |
|---|---|
| Offensive unit or player names | Local profanity list (English and Tagalog). Blocked names become the class name |
| Unsafe sprite output | Muse Image filters plus `content_policy_violation` handling, placeholder sprite |
| Gore or cruelty in narration | System prompt rules plus a local banned-word check. Failing lines replaced by the line bank |
| Cultural stigma | No real place names in GM output. Local check against a list of province and city names |
| Faces in camera view | Warped crop covers the play area only. Calibration says "Itutok ang camera sa mesa lang." |

## Review checklist (before recording)

- [ ] Every line bank and copy line read aloud by 2 Filipino playtesters, edits recorded in `docs/playtests.md`
- [ ] Glossary entries checked for accuracy and tone
- [ ] Enemy sprites cute-spooky, no gore
- [ ] GM system prompt includes every hard rule
- [ ] Banned-word list and place-name list loaded and tested
- [ ] Profanity filter tested on English and Tagalog samples
- [ ] Demo friends gave written OK for likeness (Q9)

## Sources and lists

The profanity, banned-word and place-name lists are local data files. Their location and format: `architecture/ai-contracts.md`. Do not commit offensive word lists in plain sight of the README. Keep them in a data folder with a neutral name.
