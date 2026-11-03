---
title: Screens
purpose: Every screen with purpose, elements, entry, exit and all UI states
read_when: [building or changing a screen in app/src/renderer/src/screens]
canonical_for: [screen list, screen states, screen routing]
sources: [docs/DeskTop_PRD.md#11-ux-and-ui, docs/DeskTop_PRD.md#7-solution-overview-and-key-flows, docs/DeskTop_PRD.md#14-edge-cases-and-failure-handling]
status: active
last_verified: 2026-11-03
related: [docs/design/DESIGN.md, docs/design/hud-components.md, docs/design/copy-deck.md, docs/game/state-machine.md]
---

# Screens

Twelve screens, each a component in `app/src/renderer/src/screens/`, routed by `App.tsx` from backend state. Every screen handles loading, error, offline and Demo Safe Mode states.

## Key facts

| Fact | Value |
|---|---|
| Screens | Start, KeySetup, Calibration, Summon, UnitCard, VoiceClaim, Night, Sunrise, Defeat, Replay, Campaign menu, Settings |
| Router | `App.tsx`, driven by the backend game state |
| Text | All from `lib/copy.ts` keys |
| Settings screen | Cut (ADR-0112), not built |

## Shared states (every screen)

| State | Trigger | Shows |
|---|---|---|
| Connecting | Backend starting or restarting | `restore` "Sandali, ibinabalik ko ang laro..." |
| Offline model | Breaker open | `net.down` banner naming the feature, tap controls stay |
| Slow network | p90 over 2x target for 3 calls | `net.slow` banner |
| Credits low | Hard stop hit | `credits.low`, Demo Safe Mode on |
| Demo Safe Mode | Toggle on | Small "Demo Safe" badge in the top band |
| Paused | Camera moved | `cam.moved` overlay, Recalibrate action |

## Screen specs

| Screen | Purpose | Key elements | Enter | Exit |
|---|---|---|---|---|
| LanguagePick | First-run language | Logo, Filipino and English buttons | No language stored | Language saved, routes to KeySetup or Start |
| Start | Begin or continue | Logo, tagline, New Campaign, Continue, Settings, Demo Safe Mode toggle, credit meter (dev build only), `start.ready` | App launch | New, Continue, Settings |
| KeySetup | First-run API key | Paste field (masked), Save, short privacy note | No stored key | Key saved through main process safeStorage |
| Calibration | Map the desk | Live feed, A4 outline guide, 4 corner handles, play-area rectangle (default 60 x 40 cm), ruler check, Done. Copy `calib.place`, `calib.tap`, `calib.done`, `calib.dark`, "Itutok ang camera sa mesa lang." | First launch, camera moved, Settings recalibrate | Homography saved |
| Summon | Create units | Warped feed, `summon.prompt`, roster sidebar (max 12), kubo slot highlighted first, Begin Night, typed name input | Start Night | Begin Night with valid roster |
| UnitCard | Show a new unit | Sprite (placeholder then real), name, class, HP, ATK, move, range, power, Taglish and English text, owner chip, Rename, Re-roll (1 per unit) | New unit registered | Auto-dismiss or tap |
| VoiceClaim | Map voices | `claim.prompt`, speaker chips A to D with names, Skip, `claim.who` | Begin Night | All claimed, Skip, 60 s timeout |
| Night | Play | Board plus full HUD (see `hud-components.md`) | Voice claim done | Sunrise or Defeat |
| Sunrise | End of night | Dawn sky, score, Bayani ng Gabi, badges (Could), Replay (consent only), Next Night, Quit, `win` | Turn 8 survived | Replay, Next Night, Quit |
| Defeat | Lost night | Fallen kubo art, score, Try Again, `lose` | Kubo HP 0 or no units | Try Again, Quit |
| Replay | Make and find the reel | `components/ReplayPanel.tsx` on Sunrise and Defeat: Make the Replay, `replay.making` while rendering, Show in folder when done, Try again on failure | Night ended with consent | Next Night or Quit |
| Campaign menu | Manage saves | Campaign list, nights survived, units, Delete campaign with confirm | Continue | Select or back |
| Settings (Could) | Preferences | Camera, mic, caption language, difficulty, replay on or off, TTS on or off (default off), show real objects, recalibrate | Start | Back |

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
| Night | Blocked End Turn | `endturn.blocked`, ghosts |
| Replay | No consent | Replay button hidden on Sunrise |
| Replay | SAM video failed | Fallback 10 s clip or skip |

## Consent screen

Built 2026-10-29 as a section of the VoiceClaim screen after Begin Night, not a separate screen. Each claimed player taps Payag or Hindi.

Copy `rec.consent`. Every claimed player must answer Payag for recording to start (FR-44). No answer counts as no. No consent: the night plays without recording and the replay panel stays hidden.

## Design review

Run `impeccable critique` and `impeccable audit` on each built screen, then `impeccable-finish-reviewer` (Sonnet, medium effort) on the finished set.
