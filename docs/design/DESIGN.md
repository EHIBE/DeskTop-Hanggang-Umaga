---
title: Design system
purpose: Visual tokens, typography, components, layout, motion and bans for every DeskTop screen
read_when: [any UI work, choosing a color or size, reviewing a screen]
canonical_for: [color tokens, type scale, sizing rules, motion rules, visual bans]
sources: [docs/DeskTop_PRD.md#art-direction, docs/DeskTop_PRD.md#hud-layout-1920x1080, docs/DeskTop_PRD.md#10-non-functional-requirements]
status: active
last_verified: 2026-10-28
related: [docs/design/screens.md, docs/design/hud-components.md, docs/design/art-direction.md, docs/design/accessibility.md]
---

# Design System: DeskTop: Hanggang Umaga

A cute-spooky 16-bit night over a real desk, readable from across a table. This file encodes the PRD art direction as tokens. It adds role names and states but no new visual direction.

## Key facts

| Fact | Value |
|---|---|
| Style | Top-down 16-bit pixel art, cute-spooky, readable silhouettes |
| Palette | Gabi 16 (locked core) |
| Target display | 1920x1080 on a laptop, read from about 1 m |
| Font | Open-license pixel font, 8 px base at 2x (16 px minimum at 1080p) |
| Scaling | Integer only, nearest-neighbor |
| Token home in code | `app/src/renderer/src/assets/main.css` as CSS variables (Tailwind v4 `@theme`), mirrored in `assets/palette.json` |
| Surface mode | Operate (HUD) wrapped in Experience (the board). Precision and readability first |

## 1. Visual theme and atmosphere

A barrio at night seen from above. The real desk shows through, dimmed to 40% with a night blue tint, so players always see their own objects. Lantern light pools around the kubo. A moon highlights the top right. The forest edge is a dark vignette where creatures appear. At sunrise everything warms over 3 seconds. Density is high on the board and low in the HUD bands. Motion is small and purposeful: sprite bobs, ring pulses, arrow draws, floating numbers.

## 2. Color palette and roles

Hex values are canonical (PRD). Role names are this file's assignment.

| Token | Hex | Role |
|---|---|---|
| `--gabi-ink` | #0B0E1A | Sprite outline (1 px), deepest background, text shadow |
| `--gabi-night` | #1B2238 | HUD panel fill |
| `--gabi-dusk` | #2E3A5C | Panel border, inactive chip fill |
| `--gabi-slate` | #4A5D8A | Disabled, downed unit grey-out tint |
| `--gabi-mist` | #8FA3C7 | Secondary text, English caption line |
| `--gabi-moon` | #E8EEF7 | Primary text, Taglish caption line |
| `--gabi-lantern` | #F2C14E | Primary accent: kubo HP, End Turn button, focus ring, Bayani ng Gabi |
| `--gabi-ember` | #E07A2E | Warnings, damage numbers on units, net.slow banner |
| `--gabi-sindak` | #B33A3A | Enemy intent arrows, illegal move ring, REC dot, defeat |
| `--gabi-ube` | #6B2D5C | Manananggal accents, night sky gradient |
| `--gabi-kawayan` | #3E7D4F | Legal move ring, success |
| `--gabi-dahon` | #7FB069 | Healthy HP bar, heal numbers |
| `--gabi-nipa` | #8C5A3C | Hut and fence tiles |
| `--gabi-buhangin` | #C99A6B | Dirt path tiles, neutral highlights |
| `--gabi-bukang` | #F4A6A0 | Dawn sky low |
| `--gabi-liwayway` | #FFD9A0 | Dawn sky high, sunrise title |

Rules:
- One accent (lantern gold) for actions and focus. Red is only for threat and error.
- Sprites quantize to these 16 plus up to 8 colors sampled from the object.
- Never pure #000000 or #FFFFFF.
- Color never carries meaning alone (see `accessibility.md`).

## 3. Typography rules

| Role | Spec |
|---|---|
| Base | Pixel font, 8 px design size rendered at 2x (16 px) minimum at 1080p |
| Body and captions | 16 px (2x), Taglish line in moon, English line below in mist |
| Labels and chips | 16 px (2x) |
| Phase banner, turn counter | 24 px (3x) |
| Sunrise and defeat titles | 48 px (6x) |
| Numbers | Same pixel font, tabular if the font allows |

- Only integer multiples of the base size.
- Caption lines max about 40 characters per line at 2x before wrapping (Unverified, tune on device).
- Font file and license live in `assets/fonts/`. Font choice is open (PRD says open-license pixel font).

## 4. Component stylings

Full state tables: `hud-components.md`.

- Buttons: flat pixel boxes, 2 px ink border, lantern fill for the single primary action (End Turn, Begin Night, Start Night), dusk fill for secondary. Pressed state shifts 1 px down. Focus shows a 2 px lantern outline.
- Chips (orders, speakers): dusk fill, moon text, X target 48 px or larger.
- Panels: night fill with dusk 2 px border, square corners. No soft shadows, no blur.
- Rings and arrows: drawn on canvas, pixel-aligned, shape plus color.
- Cards (unit card only): night panel with the sprite at integer scale, stats in a grid.
- Loading: "Sandali..." copy with a 2-frame pixel lantern blink. No spinners.
- Empty states: instruction copy from the copy deck (for example `summon.prompt`).
- Errors: inline banner with copy-deck text and an action. Never a raw error message.

## 5. Layout principles

- Fixed 16:9 stage at 1920x1080 scaled by integer steps. Letterbox with ink.
- Top band: turn counter, phase banner, kubo HP. Bottom band: speaker chip and caption, order chips, unit strip, End Turn. Board in the middle. See `hud-components.md` for the HUD map.
- Spacing unit 8 px (one font pixel at 1x). Gaps are multiples of 8.
- Nothing overlaps the play area except sprites, rings, arrows, ghosts and floating numbers.
- Tap targets 48 px or larger (players tap from a seated position).

## 6. Motion and interaction

| Motion | Spec |
|---|---|
| Sprite snap after re-anchor | 200 ms ease |
| Sprite follow | Tracker positions smoothed with EMA alpha 0.4 |
| Enemy idle | 2-frame bob |
| Enemy defeat | Poof of smoke, no gore |
| Speaker chip | Pulses while speaking |
| Dawn | 3 s palette shift |
| Floating numbers | Rise and fade, about 600 ms (Unverified, tune) |
| Performance | Canvas at 30 FPS or more (NFR-09). Animate transform and opacity only in DOM |

Animations start from rules events at once. They never wait for narration.

## 7. Anti-patterns (banned)

- Gore, blood splatter, body horror
- Smooth or bilinear scaling of pixel art, non-integer scales
- Gradients, glows, blur, soft drop shadows on UI chrome
- Color-only state (a ring must also change shape and icon)
- Text under 16 px at 1080p
- Emojis in UI copy
- Raw English-only error text, stack traces, or model output shown unfiltered
- Real place names attached to monsters
- Generic placeholder names in demo content
- Spinners that block play

## Implementation notes

- Tailwind v4 is installed but not wired yet (ADR-0102). Define tokens in an `@theme` block once wired.
- Use `image-rendering: pixelated` on every canvas and sprite image.
- Keep the scaffold styles (`base.css`, wavy lines, Electron logo) out of the game screens. Replace them when building Start.
