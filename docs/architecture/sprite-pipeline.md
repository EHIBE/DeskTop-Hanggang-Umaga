---
title: Sprite pipeline
purpose: Step-by-step spec for turning an object crop into a keyed 48x48 sprite, plus cache and fallbacks
read_when: [implementing backend/vision/sprites.py, tuning sprite quality]
canonical_for: [sprite steps, sprite prompt template, cache key, sprite validation, recording and replay pipeline]
sources: [docs/DeskTop_PRD.md#sprite-pipeline, docs/DeskTop_Build_Guide.md#phase-5-sprite-pipeline-oct-29-to-30-4-h-f03, docs/DeskTop_PRD.md#flow-f8-replay, docs/DeskTop_Build_Guide.md#phase-14-replay-reel-nov-4-morning-4-h-f15]
status: active
last_verified: 2026-10-28
related: [docs/design/art-direction.md, docs/decisions/ADR-0005-chroma-key-sprites.md, docs/architecture/meta-api-integration.md]
---

# Sprite pipeline

Each new unit shows a class placeholder at once, then a background job turns its masked crop into a keyed, palette-locked 48x48 sprite. The same file covers the replay video pipeline, the other heavy media path.

## Key facts

| Fact | Value |
|---|---|
| Module | `backend/vision/sprites.py` |
| Model | muse-image-1.0, reasoning strength low, 1024x1024 PNG |
| Target latency | 30 s p90, never blocks play (NFR-02) |
| Output | 48x48 PNG with alpha, 1 px #0B0E1A outline |
| Accept | Alpha coverage 15% to 90%, at least 2 non-key colors |
| Cache | `sprite.cache_key` unique, PNG on disk |

## Steps

| Step | Spec |
|---|---|
| 1 | Crop the full-resolution warped frame to the SAM mask box padded 15% |
| 2 | Fill pixels outside the mask with flat #808080 |
| 3 | Resize so the long side is 512 px, PNG |
| 4 | Key color #FF00FF, or #00FF00 if the dominant hue is within 30 degrees of magenta |
| 5 | Build the prompt (below). Add the style anchor as a second image once one exists |
| 6 | Muse Image call (`meta-api-integration.md` call 12) |
| 7 | Chroma key: pixels within HSV distance 40 of the key color to alpha 0. Erode alpha by 1 px |
| 8 | Trim, nearest-neighbor downscale into 48x48, quantize to Gabi 16 plus 8 object colors, add the outline |
| 9 | Validate. Fail: regenerate once with the other key color. Fail: SAM concept cutout of the sprite image with the noun label. Fail: keep the placeholder |
| 10 | First accepted sprite of a campaign becomes the style anchor (`campaign.style_anchor_sprite_id`) |

## Prompt template

```text
Redraw the object in this photo as one top-down 16-bit pixel art game sprite of [sprite_subject_en], a [class] defender in a Filipino folklore night game. Keep the object's main colors and silhouette so it is recognizable. Centered, fills about 80% of the frame, no shadow, no text, no border. Solid flat [key color] background.
```

With a style anchor, append: "Match the pixel art style of the second image."

## Cache

`cache_key = sha256(object_signature_id + "|" + normalized_unit_name + "|" + class + "|" + palette_version + "|" + prompt_version)`. A hit logs no Muse Image call (FR-13). Bump `prompt_version` whenever the template changes.

## Failure handling

| Failure | Response |
|---|---|
| HTTP 400 `content_policy_violation` | Placeholder, no retry with the same prompt |
| Timeout 45 s or breaker open | Placeholder |
| Keying fails (purple object) | Other key color, then SAM cutout, then placeholder |
| Hard stop reached | Placeholder, Demo Safe Mode |

## Built (2026-10-28)

| Part | Where |
|---|---|
| Crop, key colour, chroma key, finalize, validate, cache key, prompt | `backend/vision/sprites.py` (pure functions, 95% coverage) |
| Muse Image call, other-key retry, SAM concept cutout, content-policy placeholder | `MuseImageGenerator` in `vision/sprites.py` |
| Cache first, then generate, save, link unit, style anchor | `SpriteService` in `vision/sprites.py`, rows and files through `db/store.py` (`sprites/<uuid>.png` under the data root) |
| Background job and push to the renderer | `GameController._schedule_sprite`, `sprite` WebSocket message |
| Class placeholders and enemy art | `backend/smoke/assets.py` (Manual: EHIBE, needs the key, about $0.15) |

HSV distance as built: OpenCV HSV, hue difference with wraparound scaled so 90 OpenCV units equal 255, then Euclidean with the saturation and value differences. Pixels at distance 40 or less become transparent, then the alpha erodes by 1 px. Opaque means alpha 128 or more. Object colours come from a deterministic median cut.

A re-roll that changes the class starts a new sprite job and cancels the older one, and a stale result is dropped. A rename keeps the current sprite (privacy and cost audit, M5), so a later cache lookup under the new name misses and the unit keeps its existing sprite. The sprite subject is Spark's filtered `sprite_subject_en` or a fixed fallback, never the player name. A cache hit costs nothing.

## Note on keying math

PRD specifies HSV distance 40. The Build Guide sample uses an RGB absolute-sum tolerance of 60 per channel. Implement the PRD rule and test both on the 20 saved outputs before choosing.

## Recording and replay pipeline

| Step | Spec | FR |
|---|---|---|
| 1 | Consent from every claimed player before recording | FR-44 |
| 2 | Pipe warped frames to ffmpeg: rawvideo bgr24 in, libx264 veryfast crf 23, yuv420p, `+faststart`. List args only, never a shell | FR-45 |
| 3 | At sunrise pick 4 to 6 highlights from turn_log (kubo hits, kills, manananggal split, last turn), about 8 s each | FR-46 |
| 4 | Cut each to 10 FPS, 960 px wide, then concat into a proxy MP4 (about 400 frames) | FR-47 |
| 5 | Upload with `expires_after` 86,400 s | FR-47 |
| 6 | One SAM video request with box prompts on the first frame of each segment, `propagation_direction: forward` | FR-47 |
| 7 | DELETE the uploaded file right away | NFR-22 |
| 8 | Render locally at 1080p 30 FPS: real footage, sprites pinned to SAM tracks (interpolate between 10 FPS frames), damage numbers from turn_log, dawn title card, 60 s max | FR-48 |

Fallback: if SAM video fails, keep one 10 s SAM-tracked clip. Red REC dot shows while recording.
