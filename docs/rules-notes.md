---
title: Official Rules notes
purpose: Answers from the Official Rules and findings from Phase 0 and Phase 1 checks
read_when: [Official Rules arrive, after smoke tests, before submission]
canonical_for: [Official Rules answers, smoke test findings]
sources: [docs/DeskTop_Build_Guide.md#01-account-and-rules-checks, docs/product/open-questions.md]
status: active
last_verified: 2026-10-28
related: [docs/product/open-questions.md, docs/architecture/meta-api-integration.md, docs/delivery/submission-checklist.md]
---

# Official Rules notes

Record answers from the Official Rules here with the exact rule text or link. As of 2026-10-28 nothing is recorded.

## Key facts

| Item | Status |
|---|---|
| Official Rules read | Not recorded |
| Credits claimed | Not recorded |
| Standard mode confirmed | Not recorded |
| Structured output layout (A6) | Not tested |

## Rules checklist

| Item | Unconfirmed note | PRD default | Official answer | Source |
|---|---|---|---|---|
| Demo video length | 3 minutes, main judging artifact | 2:30 | | |
| Repo | Public repo required | Public | | |
| Pre-existing code | Only work built during the event counts | New repo after kickoff | | |
| Model use | Pass/fail check of real Meta Model API use | 4 Meta models | | |
| Credits | Claim by Nov 4 | Claim early | | |
| Team | Max 4, one submission per team | Solo | | |
| Judging weights (A1) | 30, 25, 25, 20 | As PRD | | |
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
