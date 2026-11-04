---
title: Risk register
purpose: Every scored risk with mitigation, kill switch and live status
read_when: [daily review, a risk fires, choosing what to cut]
canonical_for: [R01 to R19, risk scores, kill switches, exposure summary]
sources: [docs/DeskTop_PRD.md#16-risk-register, docs/DeskTop_PRD.md#205-risk-exposure-summary]
status: active
last_verified: 2026-11-04
related: [docs/delivery/schedule.md, docs/product/scope-and-cuts.md]
---

# Risk register

Nineteen risks scored by likelihood times impact (1 to 5 each). Owner for every risk is EHIBE. Update the Status column when a risk fires, changes or closes.

## Key facts

| Fact | Value |
|---|---|
| Total exposure | 172 of 475 (36%) |
| Critical (15 to 25) | 1: R01 schedule |
| High (10 to 14) | 6: R02 to R07 |
| Medium (6 to 9) | 9: R08 to R16 |
| Low (under 6) | 3: R17 to R19 |

## Register

| ID | Risk | L | I | Score | Mitigation | Kill switch | Status |
|---|---|---|---|---|---|---|---|
| R01 | Schedule overload from the PayPal AI Hackathon, thesis and client work | 4 | 5 | 20 | Fixed daily blocks, Must list first, freeze, internal deadline | Cut order | Open. Build Guide added 3.5 h over the PRD plan. Post-freeze build time added (ADR-0113) |
| R02 | Official Rules add a conflict | 3 | 4 | 12 | New repo after kickoff, read rules, keep video at 2:30 | Re-scope within 24 h | Open. Rules text not recorded, event page facts only in rules-notes.md |
| R03 | Re-anchor swaps look-alike identities | 3 | 4 | 12 | Histogram signature, tracker priors, tap confirm, E2 | No identical objects in demo | Open |
| R04 | Diarization unreliable in a noisy room | 4 | 3 | 12 | Soft ownership, keywords, ENDPOINTING, PTT, tap | Tap-to-claim and ENDPOINTING only | Open |
| R05 | Sprite quality or latency poor | 3 | 4 | 12 | Reference prompt, palette lock, placeholder first, cache | Pre-generate demo sprites | Open |
| R06 | Tracker jitter or occlusion looks bad | 3 | 4 | 12 | EMA smoothing, freeze on loss, SAM snap | Slower hands, more light | Open |
| R07 | Live finals failure from outage | 2 | 5 | 10 | Demo Safe Mode, cached assets, backup recording | Play the backup recording | Open |
| R08 | Spark boxes inaccurate | 3 | 3 | 9 | Diff against known boxes, SAM refines, tap fallback | Tap-to-select only | Open |
| R09 | Taglish orders misrecognized | 3 | 3 | 9 | Keywords, grammar, chips, E3 | Tap controls carry the demo | Open |
| R10 | Judges' setup differs | 3 | 3 | 9 | Setup guide, calibration checks, dark warning | Video is the main artifact | Open |
| R11 | Packaging Electron plus Python is hard | 3 | 3 | 9 | One-command setup, pre-built zip if time | Judges watch the video and read the repo | Zip built 2026-11-04 (ADR-0111). Clean-machine run Manual: EHIBE |
| R12 | Impact scored low because it is a game | 3 | 3 | 9 | Lead with shared table, zero hardware, Taglish, folklore, real friends | Framing only | Open. See market docs |
| R13 | Credit overrun | 2 | 3 | 6 | Cost meter, fixtures, $120 stop | Demo Safe Mode | Open |
| R14 | Cultural misrepresentation | 2 | 3 | 6 | Glossary review, no place names, 2 playtesters review | Reviewed line bank | Open |
| R15 | Sprite keying fails on some objects | 3 | 2 | 6 | Key color switch, SAM cutout | Placeholder | Open |
| R16 | Webcam access problems on Windows | 2 | 3 | 6 | Backend owns camera, device picker, retry | Phone-as-webcam app | Open. B14 ffmpeg not on PATH (recording only) |
| R17 | Organizers get a perpetual license | 5 | 1 | 5 | Accepted. Nothing confidential in the repo | None | Accepted |
| R18 | Structured output layout differs | 2 | 2 | 4 | One test call in Phase 1 | Chat Completions response_format | Open |
| R19 | Content filter blocks a sprite | 2 | 2 | 4 | Neutral prompts, placeholder | Placeholder | Open |

## New risks found while writing docs (2026-10-28)

| ID | Risk | L | I | Score | Mitigation |
|---|---|---|---|---|---|
| R20 | Python env missing, empty requirements (B1) delays Phase 1 | 3 | 3 | 9 | Resolved by ADR-0101 |
| R21 | Electron scaffold insecure defaults ship (B3) | 2 | 4 | 8 | Resolved by ADR-0103 |
| R22 | Laptop ownership among target groups lower than assumed (see market docs) | 3 | 3 | 9 | Frame for one laptop per group, show classroom use |

R20 to R22 are Proposed additions. Confirm with EHIBE before counting them in the exposure total.
