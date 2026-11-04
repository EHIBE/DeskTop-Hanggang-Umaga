---
title: Demo runbook
purpose: Dry-run checklist, demo night procedure, Demo Safe Mode use and live finals plan
read_when: [before recording, before live finals, rehearsing]
canonical_for: [dry-run checklist, demo night steps, live finals plan]
sources: [docs/DeskTop_PRD.md#demo-dry-run-checklist-before-recording-and-before-live-finals, docs/DeskTop_Build_Guide.md#135-playtest-2-and-demo-recording-25-h-evening]
status: active
last_verified: 2026-11-04
related: [docs/delivery/video-script.md, docs/architecture/reliability-and-fallbacks.md, docs/design/cultural-care.md]
---

# Demo runbook

The demo is recorded on Nov 4 and may be repeated live at finals on Nov 9. No recording or playtest has been logged yet. Run the checklist each time, then play at least two full nights with recording on.

## Key facts

| Fact | Value |
|---|---|
| Recording day | Nov 4 (no recording logged yet) |
| Gate | 3 crash-free nights in a row before recording |
| Footage | Saved to 2 drives |
| Players | 2 or 3 Filipino friends with written OK |
| Checker agent | `desktop-demo-readiness-checker` (Sonnet, medium effort) |

## Dry-run checklist

- [ ] Light: even overhead light, no strong shadow, brightness check passes
- [ ] Camera: stand fixed, top-down, play area fills the frame, ruler check within 0.5 cm
- [ ] Surface: plain matte mat, nothing outside the play area
- [ ] Objects: mug, coin, keys, pen, eraser nearby, no identical pairs
- [ ] Sprites and cards for the demo set cached
- [ ] Mic: test sentence transcribes, room quiet, fan off
- [ ] Credits: balance checked, api_usage under $90
- [ ] Demo Safe Mode tested once with Wi-Fi off. A camera is still required in Demo Safe Mode
- [ ] ffmpeg check: `ffmpeg -version` works or `DESKTOP_FFMPEG` points at it (B14)
- [ ] Release zip run: unzip `release/DeskTop-1.0.0-win.zip` and play one night from it
- [ ] Backup recording of a full night on a second drive
- [ ] Screen recorder at 1080p 30 FPS with audio
- [ ] Phone on a tripod filming the table from the side for B-roll
- [ ] Laptop on power, notifications off
- [ ] Taglish lines reviewed by 2 playtesters (`cultural-care.md`)

## Demo night steps

1. Run the dry-run checklist.
2. Collect a written OK from each friend to appear in the video (Q9).
3. Start the screen recorder and the side camera.
4. Play at least 2 full nights with voice and recording on.
5. Ask each group: "Would you post this replay?" and fun 1 to 5. Log in `docs/playtests.md`.
6. Copy every file to 2 drives.

## Live finals plan

| Situation | Action |
|---|---|
| Normal | Live night with the demo object set |
| Slow network | Keep going, placeholders and local narration cover |
| API outage | Switch to Demo Safe Mode |
| Camera or tracking trouble | Recalibrate once, then Demo Safe Mode with tap controls |
| Anything worse | Play the backup recording |

## Shots the video needs from demo night

Summon split screen, voice claim chips, a dodge, a tikbalang shove, a Kapre smoke, a scar or badge, the Kagabi recap, the manananggal split with Asin, sunrise, and real reactions. Full list: `video-script.md`.
