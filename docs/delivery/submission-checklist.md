---
title: Submission checklist
purpose: Everything to finish and check before submitting to the hackathon
read_when: [Phase 15, the day of submission]
canonical_for: [submission checklist, submission description draft]
sources: [docs/DeskTop_PRD.md#submission-checklist, docs/DeskTop_PRD.md#project-description-draft-submission-form, docs/DeskTop_Build_Guide.md#153-submit]
status: active
last_verified: 2026-11-03
related: [docs/delivery/readme-outline.md, docs/delivery/video-script.md, docs/rules-notes.md]
---

# Submission checklist

Submit by Nov 4 11:00 PM SGT, well before the Nov 5 10:00 AM SGT hard deadline. Fields must match the Official Rules once they are read into `docs/rules-notes.md`.

## Key facts

| Fact | Value |
|---|---|
| Target | Nov 4, 11:00 PM SGT (15:00 UTC, 10:00 AM ET) |
| Hard deadline | Nov 5, 10:00 AM SGT (02:00 UTC, Nov 4 9:00 PM ET) |
| Fallback | Submit whatever is done by Nov 5, 8:00 AM SGT |
| Track and theme | Indie, Build for Your World |

## Checklist

- [ ] Official Rules fields filled exactly as required
- [ ] Track: Indie. Theme: Build for Your World
- [ ] Video uploaded (public or unlisted per rules), link tested in a private window
- [ ] Repo public, README complete, no API keys (secret scan run)
- [ ] Description pasted, updated with real numbers, proofread
- [ ] Every Meta model used is named
- [ ] Screenshots: summon split screen, HUD mid-night, sunrise, replay frame
- [x] License decided (D12): MIT code in `LICENSE`, CC BY-NC 4.0 assets in `assets/LICENSE-ASSETS.md`. Added 2026-11-03
- [ ] Submission confirmation screenshot saved

Pushing to GitHub needs an explicit instruction from EHIBE (`engineering/git-and-commits.md`).

## Secret scan (PowerShell)

```powershell
git log -p | Select-String -Pattern "MODEL_API_KEY|sk-|Bearer "
```

## Description draft

> **DeskTop: Hanggang Umaga** turns any desk into a turn-based co-op game. Put everyday objects on the table and say what they are. A mug becomes the bahay kubo you protect, a coin becomes an anting-anting, keys become the albularyo. Then creatures from Filipino folklore crawl in from the edges of the desk, and 1 to 4 friends have 8 turns to survive until sunrise. Players move real objects by hand and give orders out loud in Taglish.
>
> Muse Spark 1.3 detects each new object and writes its unit card, then runs the Game Master with strict JSON output. SAM 3.1 gives every object an exact mask and a stable ID through box prompts, re-anchors all pieces at each End Turn, and tracks the recorded night for a replay reel. Muse Image redraws each object as a 16-bit sprite in one shared style. Muse Voice Transcribe handles Tagalog code-switching, speaker labels and turn detection. A local OpenCV tracker keeps sprites smooth between turns, and a deterministic rules engine decides every outcome.
>
> It needs only a laptop, a webcam and an A4 sheet. Built solo for the Indie track, under Build for Your World, from General Santos City, Philippines.

Update with eval numbers and measured cost before pasting.

## After submitting (Nov 5 to 8)

Post one short clip per day with Taglish captions for the community vote, following any voting rules (`market/launch-and-community.md`).
