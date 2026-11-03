---
title: Audio
purpose: Synthesized sound cue list, mute setting and the no-TTS decision
read_when: [adding sounds, considering speech output]
canonical_for: [sound cue list, TTS policy, audio licensing]
sources: [docs/DeskTop_PRD.md#art-direction, docs/DeskTop_PRD.md#14-edge-cases-and-failure-handling, docs/design/onboarding-and-tutorial.md]
status: active
last_verified: 2026-11-04
related: [docs/design/accessibility.md, docs/architecture/voice-pipeline.md, docs/design/onboarding-and-tutorial.md]
---

# Audio

Sound sets the night mood with cues only. Every cue is synthesized at runtime with WebAudio from oscillators, noise and gain envelopes. The game ships no audio files, so there are no audio licenses to track. The game makes no speech by default, so the mic never hears the game and captions carry all narration.

## Key facts

| Fact | Value |
|---|---|
| Engine | `app/src/renderer/src/lib/sound.ts`, phase hook `lib/useSoundCues.ts`, switch `components/SoundToggle.tsx` |
| Files | None. No `assets/sfx/` folder |
| TTS | Off by default |
| Licenses | Not needed, nothing is sampled or downloaded |
| Master gain | 0.25. Ambience bed is 30% of master |
| Voices | At most 4 at once, the oldest is dropped |
| Envelopes | Ramp in at least 5 ms, out at least 20 ms |
| Mute | localStorage `desktop.sound` is `on` or `off`, missing means on. Switch in the Start footer and the Night pause overlay |
| Ducking | Not needed (no speech output) |

## Cue list

Recipes live as data in `sound.ts`. All values are Proposed and tuned by ear.

| Cue | When | Trigger in code |
|---|---|---|
| Night ambience | Night screens, from turn 1 to Sunrise, Defeat or Quit. Fades out on pause and back in on resume | `useSoundCues` bed effect and pause hold |
| Spawn gong | A new enemy id appears in the night state | `useSoundCues` enemy effect |
| End Turn bell | Phase goes PLAYER_PHASE to END_TURN_SNAPSHOT, by the button or the spoken "tapos na" | `useSoundCues` phase effect |
| Hit | `attack` or `power` event with damage on an ally, or a `kubo_hit` | `Night` events handler through `cuesFromEvents` |
| Dodge | `dodge` event, the "Nakaiwas!" floater | `Night` events handler through `cuesFromEvents` |
| Sunrise chime | Phase becomes SUNRISE | `useSoundCues` phase effect |
| Defeat tone | Phase becomes DEFEAT | `useSoundCues` phase effect |
| Smoke | `smoke` event (a kapre cloud appears). Noise burst plus a falling triangle tone | `Night` events handler through `cuesFromEvents` |
| Lost | `lost` event (a unit left the play area). Two falling tones | `cuesFromEvents` |
| Found | `found` event (the unit is back). Two rising tones, 523 and 784 Hz | `cuesFromEvents` |
| Badge | A badge pick on Sunrise. Three rising tones, 880, 1318 and 1760 Hz | `BadgePanel` calls `playCue('badge')` when `badge.pick` is sent |

Footsteps are cut for v1. Every cue pairs with a visible signal, so sound is never the only cue. Reduced motion does not affect audio.

## Behavior

- The AudioContext is created on the first pointer or key gesture and only while sound is on. Any failure is silent.
- Each cue fires once per event. Phase cues compare the previous phase in a ref, so a React re-render or a StrictMode double effect cannot repeat them.
- With sound off, nothing plays and the bed stops. Blocked localStorage still works for the session.

## TTS policy

- Off by default. Windows has no verified built-in Tagalog voice (A14) and speaker output would leak into the mic.
- If TTS is turned on in Settings (Could), the backend sends silence frames to the voice stream while TTS plays (edge case 28).
- Speakers can leak the bell or gong into the mic. Unverified. Check in a live voice night.
