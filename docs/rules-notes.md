---
title: Official Rules notes
purpose: Answers from the Official Rules and findings from Phase 0 and Phase 1 checks
read_when: [Official Rules arrive, after smoke tests, before submission]
canonical_for: [Official Rules answers, smoke test findings]
sources: [docs/DeskTop_Build_Guide.md#01-account-and-rules-checks, docs/product/open-questions.md]
status: active
last_verified: 2026-11-04
related: [docs/product/open-questions.md, docs/architecture/meta-api-integration.md, docs/delivery/submission-checklist.md]
---

# Official Rules notes

Record answers from the Official Rules here with the exact rule text or link. As of 2026-11-04 09:10 SGT the Official Rules text is not recorded. Only facts from the public event page are below, each with its source and access date.

## Key facts

| Item | Status |
|---|---|
| Official Rules read | Not recorded. Manual: EHIBE (Phase 3.1) |
| Official deadline | Nov 4, 9:00 PM ET, which is Nov 5, 10:00 AM SGT (EST is UTC-5 after Nov 1). Source: event page, accessed 2026-11-04 |
| Credits claimed | Not recorded |
| Standard mode confirmed | Not recorded |
| Structured output layout (A6) | Not tested |

## Rules checklist

| Item | Unconfirmed note | PRD default | Official answer | Source |
|---|---|---|---|---|
| Demo video length | 3 minutes, main judging artifact | 2:30 | Not stated on the event page | [Event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon), accessed 2026-11-04 |
| Repo | Public repo required | Public | | |
| Pre-existing code | Only work built during the event counts | New repo after kickoff | | |
| Model use | Pass/fail check of real Meta Model API use | 4 Meta models | | |
| Credits | Claim by Nov 4 | Claim early | | |
| Team | Max 4, one submission per team | Solo | Team size not stated on the event page. Tracks: Indie developer track for individual builders and students, Startup track for teams and founders | [Event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon), accessed 2026-11-04 |
| Judging weights (A1) | 30, 25, 25, 20 | As PRD | Unverified. The event page lists two criteria, project idea and technical skill, and says "Both criteria are weighted equally". The page reads like application review, so final judging weights wait on the Official Rules | [Event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon), accessed 2026-11-04 |
| Required submission fields | | | | |
| Community vote rules (Q2) | | | | |
| IP and license terms | Perpetual license to organizers | Accepted (R17) | | |

When a rule conflicts with a doc, update that doc and add an ADR.

## Phase 0 checks

| Check | Result | Date |
|---|---|---|
| `git --version` | git version 2.54.0.windows.1 | 2026-10-28 |
| `node -v` | v22.23.3 (npm 10.9.9) | 2026-10-28 |
| `py -3.11 --version` | Not installed. Python 3.13 and 3.14 present. Venv built on 3.13.15 (ADR-0101) | 2026-10-28 |
| `ffmpeg -version` | Not on PATH. Manual: EHIBE, install before Phase 13 | 2026-10-28 |
| Key created and stored in a password manager | Manual: EHIBE | |
| Contributor mode off | Manual: EHIBE | |

## Phase 1 environment findings

| Item | Finding | Date |
|---|---|---|
| `meta-sam-parser` | 0.1.0 installed, requires Python 3.10+. `build_object_prompt(*, size, objects)`. Exports `PromptObject`, `FramePrompt`, `PromptBox`, `PromptPoint`, `parse_responses_stream`, `decode_mask_to_raster`, `image_segmentation_format`, `video_segmentation_format` | 2026-10-28 |
| OpenCV | `opencv-contrib-python` 4.14.0.94. `cv2.TrackerKCF_create` and `cv2.TrackerCSRT_create` exist | 2026-10-28 |
| OpenAI SDK | 3.40.0 | 2026-10-28 |

## Phase 1 smoke test findings

| Call | Works | Detail (which shape worked, argument names, latency) | Date |
|---|---|---|---|
| Spark structured output (`text.format`) | | | |
| SAM box prompts and parser names | | | |
| Muse Image latency | | | |
| Voice DIARIZATION handshake | | | |
| Files `expires_after` | | | |

## How to run the Phase 1 smoke tests (Manual: EHIBE)

Built 2026-10-28. Each script logs to `api_usage` through `meta_client`, respects the $120 hard stop, scrubs secrets and saves fixtures under `fixtures/`. Run from `backend` after putting the key in `backend\.env`. Expected total spend is under $0.10.

| Step | Command | Records |
|---|---|---|
| Spark structured output (A6) | `.venv\Scripts\python -m smoke.spark` | Which of 3 request shapes worked, seconds, `spark_line.json` |
| SAM box prompts | `.venv\Scripts\python -m smoke.sam --image ..\eval\desk1.jpg --box 1,x1,y1,x2,y2 --box 2,x1,y1,x2,y2` | Masks with confidence, `sam_boxes.jsonl` and `.txt` |
| SAM concept (calibration) | `.venv\Scripts\python -m smoke.sam --image ..\eval\desk1.jpg --concept "white paper" --name sam_concept` | `sam_concept.jsonl` |
| Muse Image latency (A9) | `.venv\Scripts\python -m smoke.image --crop ..\eval\mug_crop.png --runs 20` | Min, median, max seconds, `sprite_kubo.png` |
| Voice handshake (two speakers) | `.venv\Scripts\python -m smoke.voice --mode DIARIZATION --seconds 10` | Whether languageBias and keywords were accepted, `voice_diarization.jsonl` |
| Files `expires_after` | `.venv\Scripts\python -m smoke.files --clip ..\eval\clip.mp4` | Which upload shape worked, delete result |

Inputs `eval\desk1.jpg`, `eval\mug_crop.png` and `eval\clip.mp4` (H.264) are Manual: EHIBE. Paste each script's printed result into the Phase 1 table above and the timings into `docs/eval.md`.

Verified from the installed packages and docs on 2026-10-28, before any live call: realtime events carry a `type` field, audio goes as binary PCM frames, input ends with `{"type": "endStream"}`, and the server replies to the handshake with a `sessionId`. The SDK `files.create` accepts `expires_after` directly. The structured output layout is still Unverified, because the docs page shows a different shape from the PRD, so `smoke.spark` tries both plus Chat Completions.
