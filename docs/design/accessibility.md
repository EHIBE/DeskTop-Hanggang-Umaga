---
title: Accessibility
purpose: Text, color, input and language rules so every player can play
read_when: [building or reviewing any UI, copy or input path]
canonical_for: [accessibility rules, input parity]
sources: [docs/DeskTop_PRD.md#10-non-functional-requirements, docs/DeskTop_PRD.md#11-ux-and-ui]
status: active
last_verified: 2026-10-28
related: [docs/design/DESIGN.md, docs/design/hud-components.md, docs/design/copy-deck.md]
---

# Accessibility

DeskTop is played by groups sitting around a laptop, some who will not speak and some who do not speak Tagalog. Every action works by tap, every state reads without color, and captions are always on.

## Key facts

| Rule | Requirement |
|---|---|
| Minimum text | 16 px at 1080p (8 px pixel font at 2x) | 
| Captions | Always on |
| Color | Shape plus color on rings and arrows |
| Input | Tap path for every voice action |
| Language | Taglish lines with English captions. Tagalog never required |

## Text

- Pixel font at 16 px minimum at 1080p (NFR-26).
- Captions always on. Taglish line first, English line below.
- High contrast: moon text on night panels.
- Never put text over the busy desk feed without a panel behind it.

## Color independence (NFR-27)

| Element | Without color |
|---|---|
| Legal move | Solid ring plus check |
| Illegal move | Dashed ring plus X |
| Downed unit | Grey plus no ring plus strip shows "Bagsak" |
| Intent arrow | "!" icon plus damage number |
| Uncertain | "?" badge |
| Stolen | Lock icon |

## Input parity (NFR-28, FR-25)

| Voice action | Tap path |
|---|---|
| Attack, power, heal | Tap unit, pick action, tap target |
| End Turn ("Tapos") | End Turn button |
| Cancel ("Hindi") | X on the chip |
| Summon name | Typed name field |
| Voice claim | Tap name chips, drag units |
| Push-to-talk | Hold Space |

## Language

- English, Tagalog and Taglish all accepted by voice.
- Cebuano and Hiligaynon are not supported by the voice model. Tap controls cover them.
- Folklore glossary in-app explains every creature for non-Filipino players.

## Motion and audio

- No flashing faster than 3 times per second.
- Game makes no speech by default (TTS off), so captions carry narration.
- Sounds are cues, never the only signal.

## Checks

Run `impeccable audit` on each screen. Manually check 16 px minimum at 1080p, grayscale screenshot readability, and a full night played with taps only.
