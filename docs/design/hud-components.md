---
title: HUD components
purpose: Layout of the night HUD and every component with its states and data source
read_when: [building app/src/renderer/src/hud or canvas components]
canonical_for: [HUD layout, component states, component to file map]
sources: [docs/DeskTop_PRD.md#hud-layout-1920x1080, docs/DeskTop_PRD.md#12-technical-architecture, docs/DeskTop_Build_Guide.md#74-hud]
status: active
last_verified: 2026-10-29
related: [docs/design/DESIGN.md, docs/design/screens.md, docs/architecture/websocket-protocol.md]
---

# HUD components

The night HUD frames the warped desk feed with a top band for status and a bottom band for talk and orders. Every element updates within one frame of a state change (FR-40).

## Key facts

| Fact | Value |
|---|---|
| Canvas | `canvas/Board.tsx`, `sprites.ts`, `rings.ts`, `arrows.ts` |
| DOM HUD | `hud/TopBar.tsx`, `UnitStrip.tsx`, `Captions.tsx`, `OrderChips.tsx`, `TapMenu.tsx`, `Narration.tsx`, `VoiceControls.tsx`, `RecIndicator.tsx`, `StatusBadge.tsx` |
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
| [Speaker: A Migs]  caption: "Spearman, saksakin ang aswang!" |
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
| Intent arrow | arrows.ts | Red, "!" icon at head, damage number. Hidden inside kapre smoke (smoke cut) |
| Unit badge | sprites.ts | "?" uncertain, lock when stolen, scar mark (Could) |
| Sprite | sprites.ts | Placeholder, real, greyed (down), blue night tint, dawn tint |
| Speaker chip | Not built (M11 shows the label inline in Captions and OrderChips) | Label and name, pulses while speaking, "?" when unknown |
| Captions | Captions | Partial (replaces, never appends), final, GM narration Taglish line plus English caption |
| Order chips | OrderChips | Pending (cancelable by "hindi" or X), resolving, removed |
| Unit strip | UnitStrip | Name, HP n/max, cooldown CD n, down, stolen, uncertain |
| End Turn button | Night | Enabled in PLAYER_PHASE, disabled otherwise, "TAPOS / END TURN" |
| Tap menu | TapMenu | Tap unit, then Attack, Power, Heal, then target. Same chip as voice. End Turn and Cancel |
| REC dot | TopBar | Red dot plus `rec.on` while recording |
| Banners | TopBar | `net.slow`, `net.down`, `credits.low`, Demo Safe badge |
| Floating numbers | Board | Damage (ember), heal (dahon), "Nakaiwas!" |

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
