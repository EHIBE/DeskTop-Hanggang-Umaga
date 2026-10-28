---
title: Tracking and re-anchor
purpose: Calibration, local tracking between turns, End Turn re-anchor and the identity recovery ladder
read_when: [implementing capture/calibration.py, capture/tracker.py, vision/sam.py, vision/signature.py]
canonical_for: [calibration math, tracker behavior, re-anchor ladder, object signature]
sources: [docs/DeskTop_PRD.md#sam-usage-spec, docs/DeskTop_Build_Guide.md#phase-2-camera-and-calibration-oct-28-2-h-f01, docs/DeskTop_Build_Guide.md#phase-6-tracking-and-re-anchor-oct-30-to-31-7-h-f04--f05]
status: active
last_verified: 2026-10-28
related: [docs/decisions/ADR-0002-hybrid-tracking.md, docs/game/balance-and-tuning.md, docs/architecture/meta-api-integration.md]
---

# Tracking and re-anchor

An A4 sheet gives a top-down desk plane. Local trackers move sprites between turns, and one SAM call at End Turn snaps every object to an exact mask, with a five-step ladder for objects that do not match.

## Key facts

| Fact | Value |
|---|---|
| Warped scale | 20 px per cm, 60 x 40 cm play area gives 1200 x 800 px (ADR-0105) |
| Tracker | OpenCV KCF (CSRT if KCF drifts) from opencv-contrib-python |
| Tracking resolution | 640 px wide (boxes scaled by 640/1200) |
| Update target | 10 Hz or more with 12 objects (NFR-10) |
| Smoothing | EMA alpha 0.4 |
| Re-anchor | One SAM image call per End Turn, boxes padded 20% |
| Eval | E2 re-anchor identity 95%+ |

## Calibration (FR-02 to FR-04)

1. Open camera with `cv2.VideoCapture(index, cv2.CAP_DSHOW)` at 1920x1080 (or 1280x720).
2. Player taps the 4 A4 corners (TL, TR, BR, BL). Optional auto-detect: SAM concept "white paper", take the mask's 4 extreme corners.
3. Map to a plane with A4 = 21.0 x 29.7 cm centered at (30, 20) cm, scaled by px per cm. `cv2.getPerspectiveTransform`.
4. Warp with `cv2.warpPerspective` to play area times px per cm.
5. Ruler check: a 10 cm on-screen line matches a real ruler within 0.5 cm.
6. Save the empty-desk baseline. Compare with `cv2.absdiff` on the desk border each turn. A shift over 2 cm pauses the game (`cam.moved`).

## Between turns (FR-26, FR-27)

| Situation | Behavior |
|---|---|
| Tracker ok | Sprite follows with EMA smoothing |
| Tracker fails with hand motion | Freeze sprite at last good position |
| Visible again | Re-lock within 1 s |
| Lost over 5 s with no hand motion | One SAM call for that object (box from last good box). Max 3 per turn |
| Brightness changes over 30% | Lower tracker trust, more SAM recovery, `calib.dark` if too dark |

## End Turn re-anchor (FR-28, FR-29)

1. Freeze input. Wait up to 3 s for no hand motion (`endturn.hands`).
2. One SAM image call with every object's tracker box padded 20%, under its SAM ID.
3. Per object, apply the ladder:

| Step | Condition | Action |
|---|---|---|
| 1 | Confidence 0.5+ and IoU with tracker box 0.3+ | Accept. Snap sprite with a 200 ms ease. Re-init tracker from the SAM box |
| 2 | Confidence 0.5+ but IoU under 0.3 | Accept only if the crop histogram matches the signature (Bhattacharyya 0.35 or less). Else step 3 |
| 3 | Confidence under 0.5 or no record | One retry with a point prompt at the tracker center plus the padded box |
| 4 | Still low | One concept prompt with the noun label. Pick the closest histogram with centroid within 15 cm of last known |
| 5 | Still nothing | Keep tracker position, "?" badge, ask for a tap (`track.uncertain`) |

4. Convert mask centroid to cm: `x_cm = x_px / 20`, `y_cm = y_px / 20`.
5. Snapshot timeout 10 s: use tracker positions with "?" badges.

## Look-alike objects (R03)

- Two signatures within 0.05, or an IoU swap at re-anchor: use last tracker positions to break ties.
- Still unsure: `track.similar` and tap.
- Demo set has no identical pairs.

## Object signature

Label, HSV histogram (8x4x4 bins over the masked crop), footprint area in cm2, bounding aspect, 128 px reference crop. Match score 0.5 histogram + 0.3 area + 0.2 aspect, match at 0.8+.

## Edge cases owned here

Hand covers piece (1), hands on desk at End Turn (2), object stacked (13), zero SAM matches (14), lighting change (9), camera bumped (10), two similar objects (11), more than 16 objects (12), new object mid-night (8). Full table: `reliability-and-fallbacks.md`.

## Thresholds

All values are starting points to tune on the eval run. List: `docs/game/balance-and-tuning.md`.
