---
title: Submission text
purpose: Paste-ready drafts for the hackathon submission form with placeholders for every number that needs a real run
read_when: [filling the submission form, writing the README intro, final proofread]
canonical_for: [submission text drafts, submission placeholders]
sources: [docs/delivery/submission-checklist.md, docs/market/launch-and-community.md, docs/market/positioning-and-messaging.md, README.md, docs/eval.md]
status: draft
last_verified: 2026-11-04
related: [docs/delivery/judging-scorecard.md, docs/delivery/submission-checklist.md, docs/market/launch-and-community.md, docs/how-to-run.md]
---

# Submission text

These are paste-ready drafts for the submission form. Every number shown as [MEASURED: ...] must come from a real run before pasting. The base draft lives in `docs/delivery/submission-checklist.md` and the roadmap in `docs/market/launch-and-community.md`.

## Key facts

| Fact | Value |
|---|---|
| Track and theme | Indie, Build for Your World |
| Players | 1 to 4 |
| License | MIT for code, CC BY-NC 4.0 for original assets |
| Fields | Must match the Official Rules once recorded in `docs/rules-notes.md` |
| Rule | Fill each placeholder from `docs/eval.md`, the `api_usage` table or the test run. Delete the brackets only after that |

## Project name

DeskTop: Hanggang Umaga

## Tagline

DeskTop: any desk is a game board.

## Short description

Draft (under 300 characters):

> Put a mug, coins and keys on your desk and they become pixel art defenders. One to four friends slide the real objects and give orders out loud in Taglish to survive Filipino folklore creatures until sunrise. Built on four Meta models.

Length check: count characters on submit day against the form limit. Unverified until counted.

## Long description

### Problem

Friends sit at the same table but play on separate screens. Tabletop games need things to buy and rules to learn, and most games do not speak the language or tell the stories a Filipino barkada grew up with.

### What it does

DeskTop: Hanggang Umaga turns any desk into a turn-based co-op game for 1 to 4 players. A top-down webcam sees the desk. Players put an object down and say what it is. A mug becomes the bahay kubo to protect, a coin becomes an anting-anting, keys become the albularyo. Creatures from Filipino folklore crawl in from the edges of the desk, and the group has 8 turns to survive until sunrise. Players move real objects by hand and give orders out loud in Taglish. The kapre blows smoke that blocks attacks, and an object knocked off the table is flagged until it comes back. After the night, the game can render a replay of real hands with the pixel battle pinned on top. Campaigns carry on: objects that return are recognized with their sprite, badges and scars, the barrio levels up, and the next night opens with a short recap of the last one.

### How the Meta models are used

| Model | Job |
|---|---|
| Muse Spark 1.3 | Detects each new object and writes its unit card from fixed enums in one call, narrates each turn as the Game Master in Taglish with English captions, parses spoken orders the local grammar missed, and writes the Kagabi recap |
| SAM 3.1 | Cuts an exact mask from the Spark box, gives each object a stable ID, re-anchors every piece at End Turn, and tracks the recorded night for the replay |
| Muse Image 1.0 | Redraws each object as a 16-bit sprite in one shared style |
| Muse Voice Transcribe 1.0 | Streams Taglish speech with speaker labels for spoken orders and voice claim |

Each model sits in a multi-step workflow. Summon: Spark detects the object and writes its card in one call, SAM masks it, the rules engine clamps the stats, Muse Image draws the sprite. Turn: a local tracker follows objects, SAM re-anchors, the rules engine resolves, Spark narrates. Voice: Voice Transcribe labels speakers, local grammar maps speech to commands, the rules engine checks them. Replay: the proxy clip is uploaded with consent, SAM tracks the video, local code renders the reel. Details: `docs/delivery/judging-scorecard.md`.

### How it is built

Electron with a React and TypeScript renderer talks over a token-protected WebSocket on 127.0.0.1 to a FastAPI backend with OpenCV and SQLite. A deterministic rules engine owns every number, and models only choose from enums or narrate. All Meta calls go through one client with timeouts, retries, a circuit breaker and a cost meter. Demo Safe Mode plays a full night offline. The API key is kept in Windows safeStorage. Tests: 2,182 backend tests and 84 renderer tests pass, all offline, with 96% backend line coverage (run 2026-11-04 08:59 SGT at commit 4b90671, re-read on submit day if the code changes). Rules determinism (E7): 50 of 50 identical boards, last run 2026-11-04 in `docs/eval.md`.

Measured results to fill in:

| Item | Value |
|---|---|
| Cost per night | [MEASURED: average from api_usage over played nights] |
| E1 registration | [MEASURED: IoU 0.5 rate from `eval/run_eval.py e1`] |
| E5 sprite first-try acceptance | [MEASURED: rated 20 objects] |
| E6 latency p90 | [MEASURED: NFR-01, 03, 05, 08 from `eval/run_eval.py e6 --db`] |
| Playtest groups | [MEASURED: number of groups and players from `docs/playtests.md`] |

Privacy: full camera video never leaves the laptop. Only warped frames, object crops, live mic audio, text with players as P1 to P4, and (with consent) a 960 px replay proxy go to Meta. One empty-desk photo goes only if the map setting is on. Every response call sets store false. The proxy expires in 24 hours and is deleted after tracking.

### What is next

Regional folklore packs, a classroom mode, a phone as the camera, a wave editor, a GM voice, more languages if the voice model adds them, and the local Glimmer recap in the zip build. Summon is by typed name today and voice summon is not built. Known limits are listed in `README.md`.

## How to run for judges

| Path | Steps |
|---|---|
| Zip | Download `DeskTop-1.0.0-win.zip` (323.8 MB, SHA-256 in `docs/delivery/release-and-packaging.md`) from [MEASURED: GitHub release link, set after EHIBE uploads the zip]. Unzip to a folder you can write to. Run the app executable inside. The build is unsigned, so Windows SmartScreen may ask to confirm. Play offline needs no key |
| From source | Install Node.js 20.19+, Python 3.13 and Git. Clone the repo, run `npm --prefix app install`, create `backend\.venv` and install `backend\requirements.txt`, then `npm --prefix app run dev` |
| Key | Optional. Paste a Meta Model API key on the first screen, or choose Play offline for Demo Safe Mode |
| Walkthrough | `docs/how-to-run.md` |

Hardware: a Windows 10 or 11 laptop, a webcam pointing straight down and an A4 sheet. The webcam is needed even in Demo Safe Mode. ffmpeg on PATH is needed only for recording and the replay reel (`winget install Gyan.FFmpeg`).

## Built with

Electron, React, TypeScript, Tailwind, Python 3.13, FastAPI, OpenCV, SQLite, ffmpeg, Muse Spark 1.3, SAM 3.1, Muse Image 1.0, Muse Voice Transcribe 1.0. Font: Press Start 2P (SIL OFL 1.1).

## Team

EHIBE, solo, General Santos City, Philippines.

## License

MIT for code. CC BY-NC 4.0 for original assets made for DeskTop. Third-party assets keep their own licenses (`README.md`, Credits). EHIBE confirms the license files exist in the repo before submitting.

## Claims check

- Do not write "first" or "only". Canonical: `docs/market/positioning-and-messaging.md`.
- Name every Meta model with its job.
- Do not present any estimate as a result. The README cost estimate stays labeled an estimate until [MEASURED] replaces it.
- Every person quoted or shown has given written OK.

## Before pasting

- Fill every [MEASURED: ...] placeholder from a real run, or delete the line.
- Re-read the test count from a fresh test run if any code changed after commit 4b90671.
- Match field names and limits to the Official Rules.
- Test the video link in a private window.
- Save the confirmation screenshot. Checklist: `docs/delivery/submission-checklist.md`.
