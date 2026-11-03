---
title: Video script
purpose: The 2:30 demo video shot list and what each shot proves to judges
read_when: [planning demo footage, editing the video]
canonical_for: [video shot list, video length default]
sources: [docs/DeskTop_PRD.md#demo-video-script-230, docs/DeskTop_Build_Guide.md#151-demo-video]
status: active
last_verified: 2026-11-03
related: [docs/market/judging-strategy.md, docs/delivery/demo-runbook.md]
---

# Video script

A 2:30 video with a hook in the first 8 seconds, then each model shown doing its job, a full night, and the engineering underneath. Length follows the Official Rules if they set one (A2), else 2:30.

## Key facts

| Fact | Value |
|---|---|
| Length | 2:30 default (unconfirmed notes say 3:00 max) |
| Captions | Taglish burned in with English subtitles |
| Main artifact | The video is likely the main judging artifact (unverified) |

## Shot list

| Time | Shot | What is said or shown | Proves |
|---|---|---|---|
| 0:00 to 0:08 | Hook. Dark desk, a hand drops a coin. "Anting-anting!" The pixel charm glows | Caption: "Any desk is a game board." | Demo, Tooling |
| 0:08 to 0:20 | Two friends at a plain table, phones away | VO: "No console. No board game. Just your table, your barkada and the stories you grew up with." | Impact |
| 0:20 to 0:45 | Summon: mug becomes kubo, keys become albularyo, pen becomes spearman. Split screen of Spark box, SAM mask, Muse Image sprite with model names | VO: "Muse Spark finds the object, SAM 3.1 cuts its exact shape, Muse Image redraws it." | Tooling |
| 0:45 to 0:55 | Voice claim: "Ako si Migs, hawak ko ang spearman." Speaker chips P1 and P2 | VO: "Muse Voice Transcribe knows who is talking, in Taglish." | Tooling, Impact |
| 0:55 to 1:35 | Night: arrows, Taglish arguing, slide the pen, "Spearman, saksakin ang aswang!", chip, "Tapos!", re-anchor flash, hit, "Nakaiwas!". Tikbalang shoves, player slides onto the ghost | Captions of real speech | Demo, Tech |
| 1:35 to 1:50 | Turn 6: manananggal splits. Asin on the lower half | GM caption: "Humiwalay ang katawan!" | Demo |
| 1:50 to 2:05 | Sunrise. Rooster. Replay reel of real hands with the pixel battle pinned | VO: "At sunrise, SAM 3.1 tracks the whole night into a replay." | Tooling, Demo |
| 2:05 to 2:20 | Under the hood: architecture, hybrid tracking, rules engine, eval numbers, cost per night | VO: "Every number comes from the rules engine. About fifty cents a night." | Tech |
| 2:20 to 2:30 | Title card | "DeskTop: Hanggang Umaga. Built solo in 10 days in General Santos City." Repo link | Impact |

## Rules

- Use only real footage and real eval numbers from `docs/eval.md`.
- Update "About fifty cents a night" with the measured api_usage average.
- Show model names on screen whenever a model acts.
- Every person on screen has given written OK.

## Social clips (from the same footage)

Three vertical 15 to 30 s clips: "mug becomes kubo", "tikbalang shove", "sunrise replay". Plan: `docs/market/launch-and-community.md`.
