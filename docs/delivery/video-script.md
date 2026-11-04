---
title: Video script
purpose: The 2:50 demo video shot list and what each shot proves to judges
read_when: [planning demo footage, editing the video]
canonical_for: [video shot list, video length default]
sources: [docs/DeskTop_PRD.md#demo-video-script-230, docs/DeskTop_Build_Guide.md#151-demo-video]
status: active
last_verified: 2026-11-04
related: [docs/market/judging-strategy.md, docs/delivery/demo-runbook.md, docs/rules-notes.md, docs/decisions/ADR-0113-post-freeze-cut-features.md]
---

# Video script

A 2:50 video with a hook in the first 8 seconds, the live model pipeline on screen, a full night with the post-freeze features, and the engineering underneath. The length stays under the 3:00 cap noted in the unconfirmed rules (A2, D10), with 10 seconds of margin.

## Key facts

| Fact | Value |
|---|---|
| Length | 2:50 target (D10). The 3:00 cap is not stated on the event page, see `docs/rules-notes.md` |
| Captions | Taglish burned in with English subtitles |
| Footage | Real table footage only. Live model calls on a real key, not Demo Safe, except where marked |
| Main artifact | The video is likely the main judging artifact (Unverified until the Official Rules are recorded) |
| Recording | Not recorded yet. Procedure: `docs/delivery/demo-runbook.md` |

## Shot list

| Time | Shot | What is said or shown | Proves |
|---|---|---|---|
| 0:00 to 0:08 | Hook. Dark desk, a hand drops a coin. "Anting-anting!" The pixel charm glows | Caption: "Any desk is a game board." | Demo, Tooling |
| 0:08 to 0:18 | Two friends at a plain table, phones away. Title screen, FIL and ENG toggle | VO: "No console. No board game. Just your table, your barkada and the stories you grew up with." | Impact |
| 0:18 to 0:45 | Live model pipeline. Mug becomes kubo, keys become albularyo, pen becomes spearman. Split screen of the Spark box and card, the SAM 3.1 mask, then the Muse Image sprite arriving, with the "how it was made" panel and model names | VO: "Muse Spark finds the object and writes its card. SAM 3.1 cuts its exact shape. Muse Image redraws it." | Tooling |
| 0:45 to 0:55 | Voice claim: "Ako si Migs, hawak ko ang spearman." Speaker chips P1 and P2 | VO: "Muse Voice Transcribe knows who is talking, in Taglish." | Tooling, Impact |
| 0:55 to 1:30 | Night: arrows, Taglish arguing, slide the pen, "Spearman, saksakin ang aswang!", chip, "Tapos na!", re-anchor flash, hit, "Nakaiwas!". Tikbalang shoves, player slides onto the ghost | Captions of real speech | Demo, Tech |
| 1:30 to 1:42 | Turn 4: the kapre blows smoke. A unit shows "In smoke". The charm uses Liwanag and the cloud clears | GM caption from the real night | Demo, Tech |
| 1:42 to 1:52 | A hand bumps an object off the play area. "[unit] is off the table! Put it back." Slide it back | Real Lost and found captions | Demo |
| 1:52 to 2:02 | Turn 6: manananggal splits. Asin on the lower half | GM caption: "Humiwalay ang katawan!" | Demo |
| 2:02 to 2:17 | Sunrise. Rooster. Badge pick, a scar on the unit that went down. Replay reel of real hands with the pixel battle pinned | VO: "At sunrise, SAM 3.1 tracks the whole night into a replay." | Tooling, Demo |
| 2:17 to 2:27 | Next night opens. "Last night..." Kagabi recap, barrio level up, the same mug recognized again with its sprite | VO: "Your objects remember. So does the barrio." | Impact, Tooling |
| 2:27 to 2:42 | Under the hood: architecture diagram from the README, rules engine, Demo Safe Mode, measured eval numbers and cost per night | VO: "Every number comes from the rules engine." Add the cost line only if a measured api_usage average exists: [MEASURED: cost per night from api_usage]. Otherwise cut it | Tech |
| 2:42 to 2:50 | Title card | "DeskTop: Hanggang Umaga. Built solo in General Santos City." Repo link | Impact |

## Rules

- Use only real footage and real eval numbers from `docs/eval.md`.
- Replace the [MEASURED] cost line with the api_usage average after the playtest nights. Until then say nothing about cost in the VO.
- Show model names on screen whenever a model acts.
- Every person on screen has given written OK.
- If the kapre or Lost shots fail on the night, cut them and give the time to the night shot. Never stage a rules result.

## Social clips (from the same footage)

Three vertical 15 to 30 s clips: "mug becomes kubo", "tikbalang shove", "sunrise replay". Plan: `docs/market/launch-and-community.md`.
