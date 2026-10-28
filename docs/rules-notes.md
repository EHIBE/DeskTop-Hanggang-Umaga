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
| `git --version` | | |
| `node -v` | | |
| `py -3.11 --version` | | |
| `ffmpeg -version` | | |
| Key created and stored in a password manager | | |
| Contributor mode off | | |

## Phase 1 smoke test findings

| Call | Works | Detail (which shape worked, argument names, latency) | Date |
|---|---|---|---|
| Spark structured output (`text.format`) | | | |
| SAM box prompts and parser names | | | |
| Muse Image latency | | | |
| Voice DIARIZATION handshake | | | |
| Files `expires_after` | | | |
