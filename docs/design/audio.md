---
title: Audio
purpose: Sound cue list, licensing rules and the no-TTS decision
read_when: [adding sounds, considering speech output]
canonical_for: [sound cue list, TTS policy, audio licensing]
sources: [docs/DeskTop_PRD.md#art-direction, docs/DeskTop_PRD.md#14-edge-cases-and-failure-handling]
status: active
last_verified: 2026-10-28
related: [docs/design/accessibility.md, docs/architecture/voice-pipeline.md]
---

# Audio

Sound sets the night mood with cues only. The game makes no speech by default, so the mic never hears the game and captions carry all narration.

## Key facts

| Fact | Value |
|---|---|
| TTS | Off by default |
| Licenses | CC0 or properly licensed, recorded in `assets/sfx/` |
| Ducking | Not needed (no speech output) |

## Cue list

| Cue | When |
|---|---|
| Crickets and frogs ambience | Whole night |
| Footsteps per enemy type | Enemy moves |
| Gong sting | Enemy spawn |
| Soft bell | End Turn |
| Rooster | Sunrise |

## TTS policy

- Off by default. Windows has no verified built-in Tagalog voice (A14) and speaker output would leak into the mic.
- If TTS is turned on in Settings (Could), the backend sends silence frames to the voice stream while TTS plays (edge case 28).

## Licensing

- Store each file with a license note (source URL, license name, author) next to it.
- Credit all third-party audio in the README credits section.
- No unlicensed music.
