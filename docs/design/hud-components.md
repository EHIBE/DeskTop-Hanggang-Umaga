---
title: HUD components
purpose: Layout of the night HUD and every component with its states and data source
read_when: [building app/src/renderer/src/hud or canvas components]
canonical_for: [HUD layout, component states, component to file map]
sources: [docs/DeskTop_PRD.md#hud-layout-1920x1080, docs/DeskTop_PRD.md#12-technical-architecture, docs/DeskTop_Build_Guide.md#74-hud]
status: active
last_verified: 2026-11-04
related: [docs/design/DESIGN.md, docs/design/screens.md, docs/architecture/websocket-protocol.md]
---

# HUD components

The night HUD frames the warped desk feed with a top band for status and a bottom band for talk and orders. Every element updates within one frame of a state change (FR-40).

## Key facts

| Fact | Value |
|---|---|
| Canvas | `canvas/Board.tsx`, `sprites.ts`, `rings.ts`, `arrows.ts`, `smoke.ts`, `CropView.tsx` |
| DOM HUD | `hud/TopBar.tsx`, `UnitStrip.tsx`, `Captions.tsx`, `OrderChips.tsx`, `TapMenu.tsx`, `Narration.tsx`, `VoiceControls.tsx`, `RecIndicator.tsx`, `StatusBadge.tsx`, `HintStrip.tsx`, `MomentLine.tsx`, `ConfirmDialog.tsx`, `mood.ts`, `status.ts`. Shared: `components/UnitMarks.tsx`, `components/BadgePanel.tsx`, `components/Dialog.tsx` |
| Screen | `screens/Night.tsx` combines Board and HUD |
| Data | WebSocket messages, see `architecture/websocket-protocol.md` |

## Layout (1920x1080)

```text
+--------------------------------------------------------------+
| GABI 3 / 8   [Phase: Galaw at Utos]        KUBO ######--  7/10|
|                                                              |
|  forest edge (dark)                                          |
|        [enemy sprite] --red arrow 2--> [unit sprite]         |
|               (solid green ring)  (dashed red ring X)        |
|                                                              |
|                     WARPED DESK FEED + SPRITES               |
|                                                              |
| [P1 chip] caption: "Spearman, saksakin ang aswang!" |
| Orders: [Spearman → atake Aswang 2  x] [Albularyo → gamot  x]|
| Units: Spearman 4/4 | Albularyo 3/4 (CD 0) | Anting 3/3 (CD 1)|
|                                      [ TAPOS / END TURN ]    |
+--------------------------------------------------------------+
```

## Components and states

| Component | File | States |
|---|---|---|
| Turn counter | TopBar | "GABI n / 8" |
| Phase banner | TopBar | Dumarating sila (spawn), Galaw at Utos (player phase), Sinusuri (snapshot), Labanan (resolution) |
| Kubo HP bar | TopBar | Lantern fill, number n/max, flashes on `kubo.hit` |
| Move ring | rings.ts | Hidden (cannot move), solid green with check (legal), dashed red with X (too far), grey (down) |
| Start ghost | rings.ts | Outline at turn start position while a move is illegal |
| Push ghost | rings.ts | Outline at push target, `tik.push` |
| Return mark | rings.ts | Mark where a freed duwende victim goes back |
| Intent arrow | arrows.ts | Red, "!" icon at head, damage number. Hidden inside kapre smoke. A smoked unit cannot hit an enemy outside every cloud (rules engine, FR-36) |
| Unit badge | sprites.ts | "?" uncertain, lock when stolen, smoke badge when `smoked` |
| Sprite | sprites.ts | Placeholder, real, greyed (down), blue night tint, dawn tint |
| Speaker chip | Built 2026-11-03 in `components/SpeakerChip.tsx`, used by Captions, OrderChips and VoiceClaim. Slot is the speaker's position in `night.players`, anything else shows "?" | Shape glyph and P1 to P4 label, pulses while a partial caption is live, "?" when unknown |
| Hint strip | HintStrip, `lib/tutorial.ts` | `.banner` above the captions row, 56 px high, one 24 px line with an arrow icon, Got it and Skip all buttons. Shows only in PLAYER_PHASE of turns 1 to 3, one hint at a time, advances on dismiss or after 8 s. Seen ids per campaign in `desktop.tutorial`. The slot is decided from the seen set captured when the night screen mounted. It stays reserved on turns 1 to 3 if any hint was unseen at mount, even after Skip all, and goes away only when turn 4 starts, so the board never shifts mid-turn. Spec: `onboarding-and-tutorial.md` |
| Smoke layer | `canvas/smoke.ts`, drawn by `Night.tsx` after the sprites | One cloud per entry in `night.smoke`: 12 px cells in mist and slate that shift every 600 ms (frozen under reduced motion), a dashed ring at the real radius and a `smoke.label` tag above. The board counts as having enemies while smoke exists |
| Barrio map layer | `Night.tsx`, `lib/assets.ts` (`AssetsContext`), `useBitmap` | When `state.map.ready`, `App.tsx` sends `map.get`. The PNG is drawn nearest-neighbor over the play area under the sprites. Absent when the setting is off or no map exists |
| Real object crop | `canvas/CropView.tsx` | 256 px canvas on the UnitCard showing the camera crop from `crops`, integer scale up and nearest-neighbor. Only when show real objects is on |
| UnitMarks | `components/UnitMarks.tsx` | Heart icon per HP badge, bolt per cooldown badge, scar icon with a count above 1. Hidden when none. `role="img"` with a combined label. Used in UnitStrip, the Summon roster and UnitCard |
| MomentLine | `hud/MomentLine.tsx`, `hud/mood.ts` | `role="status"` strip with a mood tag and the moment text in the caption language. The router clears it after 8 s. Night shows it bottom center 900 px wide, Summon top left, Sunrise and Defeat inline |
| ConfirmDialog | `hud/ConfirmDialog.tsx`, `components/Dialog.tsx` | Modal over PLAYER_PHASE when `pending_confirm` is set (strict ownership). Text from `text_tl` or `text_en`, `role="timer"` countdown (lantern colour and a "!" at 5 s or less), Don't and Go ahead (autofocus). Escape cancels. Sends `confirm.accept` or `confirm.cancel` |
| BadgePanel | `components/BadgePanel.tsx` | On Sunrise from `progression.badge_offers`: per unit an HP or cooldown choice sends `badge.pick` |
| Lost and smoked status | `hud/status.ts` (`nightUnitEntries`) | Status kinds out, stolen, lost and smoked. The `off_desk` tag counts as lost. `status.smoked` shows when `unit.smoked` |
| Captions | Captions | Partial (replaces, never appends), final, GM narration Taglish line plus English caption |
| Order chips | OrderChips | Pending (cancelable by "hindi" or X), resolving, removed |
| Unit strip | UnitStrip | Name, HP n/max, cooldown CD n, down, stolen, uncertain |
| End Turn button | Night | Enabled in PLAYER_PHASE, disabled otherwise, "TAPOS / END TURN" |
| Tap menu | TapMenu | Tap unit, then Attack, Power, Heal, then target. Same chip as voice. End Turn and Cancel |
| REC dot | TopBar | Red dot plus `rec.on` while recording |
| Banners | TopBar | `net.slow`, `net.down`, `credits.low`, Demo Safe badge |
| Floating numbers | Board | Damage (ember), heal (dahon), "Nakaiwas!" |
| Sound switch | SoundToggle | `.btn-quiet` switch, check when on, cross when off, `sfx.on` or `sfx.off`. In the Start footer and the Night pause overlay |
| Folklore glossary | GlossaryPanel | Modal `.window` 960 px wide, max 800 px, list scrolls. Opened by `gloss.open` in the Start footer (`.btn-quiet`) and the Night pause overlay (`.btn`). Escape and Close return focus to the opener. Resume is disabled while open |

## Interaction rules

- Every voice action has a tap path (FR-25, NFR-28).
- "Hindi" removes that speaker's last chip in the same player phase (FR-22).
- Two speakers at once: drop both orders, show `cmd.overlap`.
- Order chip text: `cmd.heard` pattern "[unit] → [action] sa [target]".
- Push-to-talk: hold Space (FR-24). Show a small mic indicator while held.
- Animations play from rules events immediately. Narration arrives later.

## Rendering rules

- Canvas draws the JPEG frame, then tiles at 35% opacity, then rings, sprites, arrows, numbers.
- Desk feed dimmed to 40% with a night tint (80% when "show real objects" is on).
- Integer sprite scale that fits the object footprint, minimum 2x, nearest-neighbor.
- 30 FPS or more at 1080p (NFR-09).
