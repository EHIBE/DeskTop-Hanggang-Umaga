---
title: Art direction
purpose: Visual rules for sprites, enemies, tiles, lighting and asset production
read_when: [making or reviewing sprites, tiles, enemy art, the logo or title card]
canonical_for: [sprite style rules, asset inventory, lighting rules]
sources: [docs/DeskTop_PRD.md#art-direction, docs/DeskTop_PRD.md#sprite-pipeline, docs/DeskTop_Build_Guide.md#51-before-the-pipeline]
status: active
last_verified: 2026-11-04
related: [docs/design/DESIGN.md, docs/architecture/sprite-pipeline.md, docs/design/cultural-care.md]
---

# Art direction

Every sprite must look like its real object and like it belongs to one shared 16-bit world. Enemies, tiles and placeholders are made before play and shipped as assets. Only player units are generated live.

## Key facts

| Item | Spec |
|---|---|
| Style | Top-down 16-bit pixel art, cute-spooky, readable silhouettes |
| Sprite canvas | 48x48 px, drawn at an integer scale fitting the object footprint, minimum 2x |
| Outline | 1 px #0B0E1A |
| Quantization | Gabi 16 core plus up to 8 colors sampled from the object |
| Tiles | No tile set built. See the barrio map row in the asset inventory |
| Style anchor | First accepted sprite of a campaign |

## Asset inventory

| Asset | Count | Path | Made by | When |
|---|---|---|---|---|
| Class placeholder sprites | 8 | `assets/sprites/placeholders/` | Muse Image, keyed, committed. Not run yet (Manual: EHIBE, `python -m smoke.assets`). Folder is empty | Phase 5.1 |
| Enemy sprites (2-frame bob) | 5 types (manananggal has upper and lower) | `assets/sprites/enemies/` | Muse Image, keyed. Not run yet (Manual: EHIBE, `python -m smoke.assets`). Folder is empty | Phase 5.1 |
| Barrio map (optional) | One generated top-down map of the empty desk | Campaign map file (`vision/barrio_map.py`) | Muse Image at runtime. `generated_map` setting off by default (FR-54). No tile set built, `assets/tiles/` is empty and no code loads it | Optional |
| Palette | Gabi 16 | `assets/palette.json` | Hand (built 2026-10-28) | Phase 5 |
| Pixel font plus license | 1 | `assets/fonts/PressStart2P-Regular.ttf`, `assets/fonts/OFL.txt` | Open-license download. Built | Phase 7 |
| Demo set sprites (cached) | 5 objects: mug, coin, keys, pen, eraser | sprite cache | Pipeline | Before demo |
| App icon, logo, title card | 1 set | `app/build/`, `app/resources/` | logo-design skill | Phase 15 |

## Sprite rules

- Recognizable: keep the object's main colors and silhouette.
- Centered, fills about 80% of the frame, no shadow, no text, no border in the source image.
- After keying: trim, nearest-neighbor downscale into 48x48, quantize, outline.
- Accept only alpha coverage 15% to 90% and at least 2 non-key colors.
- Downed: grey tint. Night: blue tint. Dawn: tint removed.

## Enemy rules

- Cute-spooky, never gory. Defeat is a poof of smoke.
- Distinct silhouettes: aswang low and fast, tikbalang tall with a horse head, kapre big and tree-like with a cigar, manananggal winged upper half and a separate lower half, duwende small.
- Respectful, common folklore depictions only (`cultural-care.md`).

## Lighting

| Moment | Rule |
|---|---|
| Night | Desk feed dimmed to 40% with night blue tint. Vignette at the forest edge. Lantern glow around the kubo. Moon highlight top-right |
| Show real objects | Desk feed at 80% |
| Dawn | 3 s transition to #F4A6A0 and #FFD9A0 sky gradient, sprites lose the blue tint |

## Production tools

- Muse Image 1.0 for sprites, enemies and tiles (prompt templates in `architecture/sprite-pipeline.md`).
- `impeccable-asset-producer` agent (Sonnet, medium effort) may clean raster assets from approved references without redesigning them.
- `logo-design` and `brandkit` skills for the app icon, logo and title card. Keep them pixel-consistent with Gabi 16.
