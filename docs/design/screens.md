---
title: Screens
purpose: Every screen with purpose, elements, entry, exit and all UI states
read_when: [building or changing a screen in app/src/renderer/src/screens]
canonical_for: [screen list, screen states, screen routing]
sources: [docs/DeskTop_PRD.md#11-ux-and-ui, docs/DeskTop_PRD.md#7-solution-overview-and-key-flows, docs/DeskTop_PRD.md#14-edge-cases-and-failure-handling]
status: active
last_verified: 2026-11-04
related: [docs/design/DESIGN.md, docs/design/hud-components.md, docs/design/copy-deck.md, docs/game/state-machine.md]
---

# Screens

Eleven screens plus the Recap dialog, each a component in `app/src/renderer/src/screens/`, routed by `App.tsx` from backend state. Every screen handles loading, error, offline and Demo Safe Mode states.

## Key facts

| Fact | Value |
|---|---|
| Screens | LanguagePick, KeySetup, Start, Calibration, Summon, UnitCard, VoiceClaim, Night, Sunrise, Defeat, Settings. Recap is a dialog over Calibration, Summon and VoiceClaim. Replay is `components/ReplayPanel.tsx` on Sunrise and Defeat. The campaign list lives on Start |
| Router | `App.tsx`, driven by the backend game state |
| Text | All from `lib/copy.ts` keys |
| Settings screen | Built 2026-11-04 (ADR-0113), opened as an overlay by `App.tsx` from Start and the Night pause overlay |

## Shared states (every screen)

| State | Trigger | Shows |
|---|---|---|
| Connecting | Backend starting or restarting | `restore` "Sandali, ibinabalik ko ang laro..." |
| Offline model | Breaker open | `net.down` banner naming the feature, tap controls stay |
| Slow network | p90 over 2x target for 3 calls | `net.slow` banner |
| Credits low | Hard stop hit | `credits.low`, Demo Safe Mode on |
| Demo Safe Mode | Toggle on | Small "Demo Safe" badge in the top band |
| Paused | Camera moved | `cam.moved` overlay, Recalibrate action, Folklore button (`gloss.open`, Resume is disabled while the glossary is open), sound switch (`sfx.on` or `sfx.off`), Settings button (`settings.title`), Quit (`sunrise.quit`, then a confirm with `pause.quit_confirm`, Cancel `tap.cancel` and Quit sending `pause.quit`. The autosave stays, so Continue restores the night) |

## Screen specs

| Screen | Purpose | Key elements | Enter | Exit |
|---|---|---|---|---|
| LanguagePick | First-run language | Logo, Filipino and English buttons | No language stored | Language saved, routes to KeySetup or Start |
| Start | Begin or continue | Logo, tagline, New Campaign, Continue, Demo Safe Mode toggle, Folklore button (`gloss.open`, opens the glossary panel), Settings button (`settings.title`, gear icon), sound switch, credit meter (dev build only), `start.ready` | App launch | New, Continue |
| KeySetup | First-run API key | Paste field (masked), Save, short privacy note | No stored key | Key saved through main process safeStorage |
| Calibration | Map the desk | Live feed, A4 outline guide, 4 corner handles, play-area rectangle (default 60 x 40 cm), ruler check, Done, Back (`nav.back`, sends `calibrate.back` and returns to Start without a campaign). Copy `calib.place`, `calib.tap`, `calib.done`, `calib.dark`, "Itutok ang camera sa mesa lang." | First launch, camera moved, Recalibrate in the pause menu | Homography saved |
| Summon | Create units | Warped feed, `summon.prompt`, roster sidebar (max 12) with UnitMarks and a `unit.returning` tag on matched returning objects, a returning banner, the MomentLine for `object_recognized`, kubo slot highlighted first, Begin Night, typed name input | Start Night | Begin Night with valid roster |
| UnitCard | Show a new unit | Sprite (placeholder then real), name, class, HP, ATK, move, range, power, Taglish and English text, owner chip, UnitMarks, `unit.returning` tag, Real object toggle (`card.real`, shows the camera crop when Settings has show real objects on), Rename, Re-roll (1 per unit, disabled for returning units) | New unit registered | Auto-dismiss or tap |
| VoiceClaim | Map voices | `claim.prompt`, speaker chips P1 to P4 with names, Skip, `claim.who` | Begin Night | All claimed, Skip, 60 s timeout |
| Night | Play | Board plus full HUD (see `hud-components.md`) | Voice claim done | Sunrise or Defeat |
| Sunrise | End of night | Dawn sky, score, Bayani ng Gabi, barrio level and nights survived (`progress.level`, `start.nights`), BadgePanel (`badge.title`, one pick per offer, HP or cooldown), MomentLine, Replay (consent only), Next Night, Quit, `win` | Turn 8 survived | Replay, Next Night, Quit |
| Defeat | Lost night | Fallen kubo art, score, MomentLine, Try Again, `lose` | Kubo HP 0 or no units | Try Again, Quit |
| Replay | Make and find the reel | `components/ReplayPanel.tsx` on Sunrise and Defeat: Make the Replay, `replay.making` while rendering, Show in folder when done, Try again on failure | Night ended with consent | Next Night or Quit |
| Campaign list (on Start) | Manage saves | Campaign list, nights survived, Delete campaign with confirm | Start | Select or delete |
| Settings (ADR-0113) | `screens/Settings.tsx`. Each change sends `settings.set` and the backend stores it. Language and sound switches also stay on Start and the pause menu | Camera (locked during a night, `settings.camera_locked`), microphone, caption language, difficulty of new campaigns, replay on or off, GM voice (disabled with `settings.tts_unavailable`, there is no TTS engine), show real objects, strict ownership, generated barrio map, Back (`nav.back`) | Settings button on Start or in the pause overlay | Back |
| Recap (ADR-0113) | `screens/Recap.tsx`. Dialog titled `recap.title` with `recap.night`, the Kagabi text in the caption language, a source tag (`model.glimmer` or `model.spark`, none for the line bank) and Continue (`recap.continue`). Escape also continues | A saved recap exists and the phase is CALIBRATE, SUMMON or VOICE_CLAIM, and Settings is closed | Continue |

## Screen-specific states

| Screen | State | Shows |
|---|---|---|
| Calibration | Auto-detect found sheet | Corners pre-placed, Confirm |
| Calibration | Zero matches | Manual 4-tap |
| Calibration | Too dark | `calib.dark` |
| Calibration | Camera busy | "May ibang app na gumagamit ng camera." and device list |
| Summon | Waiting for still hand | Subtle "Sandali..." |
| Summon | Unclear new object | `summon.which`, objects tappable |
| Summon | Full | `summon.full` |
| Summon | Stacked | `summon.stack` |
| Summon | No kubo yet | Begin Night disabled, `summon.kubo_first` on tap |
| UnitCard | Sprite pending | Placeholder with a small lantern blink |
| UnitCard | Sprite failed | Placeholder stays, no error shown |
| VoiceClaim | Voice failed | Skip, tap names, drag units |
| Night | Recording | Red REC dot with `rec.on` |
| Night | Checking | `endturn.checking`, `endturn.hands` |
| Night | Held voice order | ConfirmDialog (`confirm.title`) in PLAYER_PHASE with a countdown, Go ahead or Don't |
| Night | Unit smoked or lost | Status badge `status.smoked` or `status.lost` in the unit strip and on the board |
| Night | Moment line | MomentLine at the bottom center for 8 s |
| Night | Blocked End Turn | `endturn.blocked`, ghosts |
| Night | First-night hint | Hint strip above the captions row in PLAYER_PHASE of turns 1 to 3, one line, dismiss and skip all. Voice off swaps `tut.order` to `tut.order_tap` |
| Replay | No consent | Replay button hidden on Sunrise |
| Replay | SAM video failed | Fallback 10 s clip or skip |

## Consent screen

Built 2026-10-29 as a section of the VoiceClaim screen after Begin Night, not a separate screen. Each claimed player taps Payag or Hindi.

Copy `rec.consent`. Every claimed player must answer Payag for recording to start (FR-44). No answer counts as no. No consent: the night plays without recording and the replay panel stays hidden.

## Design review

Run `impeccable critique` and `impeccable audit` on each built screen, then `impeccable-finish-reviewer` (Sonnet, medium effort) on the finished set.
