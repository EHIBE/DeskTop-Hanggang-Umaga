---
title: Assumptions and open questions
purpose: Every unverified assumption and open decision with its validation step and default
read_when: [before relying on an assumption, Official Rules arrive, after an eval or playtest]
canonical_for: [A1 to A16, Q1 to Q9]
sources: [docs/DeskTop_PRD.md#21-assumptions-and-open-questions, docs/DeskTop_Build_Guide.md#01-account-and-rules-checks]
status: active
last_verified: 2026-11-03
related: [docs/rules-notes.md, docs/eval.md, docs/playtests.md]
---

# Assumptions and open questions

Sixteen assumptions and nine open questions remain from the PRD. Update the Status column when a check runs, and record evidence in `rules-notes.md`, `eval.md` or `playtests.md`.

## Key facts

| Fact | Value |
|---|---|
| Biggest blocker | Official Rules not yet read into the repo (A1 to A4, Q1) |
| Status as of 2026-10-28 | No assumption verified in the repo yet |

## Assumptions

| # | Assumption | PRD status | How to validate | Status in repo |
|---|---|---|---|---|
| A1 | Judging weights 30, 25, 25, 20 | Unverified (third-party) | Official Rules | Open |
| A2 | Demo video of 2 to 3 minutes is acceptable | Unverified | Official Rules | Open |
| A3 | Code must be written during the build window | Unverified, conservative default | Official Rules | Open |
| A4 | Solo entry allowed on Indie track | Third-party guide | Official Rules | Open |
| A5 | Model prices and limits in the PRD | Verified 2026-10-25 on dev.meta.ai | Recheck | Open |
| A6 | Responses API structured output uses `text.format` json_schema | Partly verified | One test call (Build Guide 1.3) | Open |
| A7 | Spark boxes on 0 to 1000 grid seed SAM well enough | Unverified | E1 | Open |
| A8 | KCF or CSRT reaches 10 Hz with 12 objects at 640 px | Unverified | Benchmark (Phase 6) | Open |
| A9 | Muse Image returns a sprite within 30 s at low reasoning strength | Unverified | Time 20 calls | Open |
| A10 | Diarization separates 1 to 4 people well enough for credit | Unverified | Playtest 2 | Open |
| A11 | Voice Transcribe understands casual Taglish orders | Docs say Tagalog with code-switching | E3 | Open |
| A12 | Players find it fun and want to share the replay | Unverified | Playtests 1 and 2 | Open |
| A13 | Top-down camera setup is easy for most players | Unverified | Playtest setup time | Open |
| A14 | Windows has no verified Tagalog TTS voice | Unverified | Check Windows voices | Open |
| A15 | $150 credits arrive with acceptance | Event page | Dashboard | Open |
| A16 | Builder is accepted to the hackathon | Pending | Email | Open (build started, likely resolved) |

## Rules checklist from the Build Guide

Unconfirmed public notes from other teams. Record the real answers in `docs/rules-notes.md`.

| Item | Unconfirmed note | PRD default |
|---|---|---|
| Demo video length | 3 minutes, main judging artifact | 2:30 |
| Repo | Public repo required | Public |
| Pre-existing code | Only work built during the event counts | New repo after kickoff |
| Model use | Pass/fail check that the project truly uses Meta Model API or open weights | 4 Meta models |
| Credits | Must be claimed by Nov 4 | Claim early |
| Team | Max 4, one submission per team | Solo |

## Open questions

| # | Question | Default decision | Decide by |
|---|---|---|---|
| Q1 | What do the Official Rules require for video, repo, description? | Follow the PRD until rules say otherwise | Phase 0 |
| Q2 | How does community voting work for bonus prizes? | Post clips anyway, follow published rules | Nov 3 |
| Q3 | Code and asset license | MIT code, CC BY-NC 4.0 assets | Nov 3 |
| Q4 | Repo name | DeskTop-Hanggang-Umaga | Resolved by scaffold |
| Q5 | Strict ownership default if it ships | Off | Not shipping (Could cut) |
| Q6 | Consent from each player or one host? | Each claimed player taps Payag. Host confirm only when voice claim was skipped | Before recording |
| Q7 | Use partner credits (Modal) for Glimmer? | Only if granted and all Must and Should are done | Not shipping (Could cut) |
| Q8 | Keep "Tabi tabi po" in v1? | Yes, one line of rules code | Phase 8 |
| Q9 | Which friends play in the demo, likeness release | Two friends, written OK saved before recording | Before demo night |

## Unverified items in the PRD

Judging weights, prize table, IP license wording, Indie team size, video length, repo rules, pre-existing code rules, plus every latency and accuracy target until measured. The IP terms grant organizers a perpetual license to the submission (R17, accepted).
