# DeskTop: Hanggang Umaga

**DeskTop: any desk is a game board.**

A top-down webcam turns the everyday objects on your desk into 16-bit pixel art units. One to four friends at one table slide the real objects by hand, give orders out loud in Taglish, and defend a bahay kubo from Filipino folklore creatures for eight turns until sunrise.

Built solo by EHIBE for the Meta Global AI Developer Hackathon 2026, Indie track, theme Build for Your World.

> Demo GIF and video link: added after the demo recording (Manual: EHIBE).

## What it is

- A Windows desktop game for 1 to 4 players around one table. No phones, no controllers.
- Your mug, stapler or anting-anting coin becomes a unit with a card, a power and a pixel sprite.
- Aswang, manananggal, tikbalang, kapre and duwende attack in telegraphed waves. A deterministic rules engine decides every number, and an AI Game Master narrates in Taglish with English captions.

## How it uses Meta models

| Model | Job in the game |
|---|---|
| Muse Spark 1.3 | Finds the new object on the desk, writes its unit card from fixed enums, narrates each turn in Taglish and English |
| SAM 3.1 | Exact mask and stable id for every object, End Turn re-anchor, video tracking for the replay reel |
| Muse Image 1.0 | Redraws each object as a 16-bit sprite in one shared style |
| Muse Voice Transcribe 1.0 | Live Taglish transcription with speaker labels for spoken orders and voice claim |

Local code does the rest: OpenCV tracks objects between turns, and the rules engine decides movement, range, damage, HP, cooldowns, spawns, win and loss. Models only pick from enums and narrate. Every call goes through one client with timeouts, retries, a circuit breaker and a cost meter that warns at $90 and stops paid calls at $120. Details: `docs/architecture/meta-api-integration.md`.

## Architecture

```text
Electron (React + TypeScript, sandboxed renderer)
   |  WebSocket on 127.0.0.1 with a per-launch token
FastAPI backend (Python 3.13)
   |-- capture: webcam, A4 calibration, KCF trackers, ffmpeg recorder
   |-- vision: Spark summon, SAM masks and re-anchor, sprites, SAM video
   |-- voice: realtime transcription, Taglish grammar, voice claim
   |-- gm: line bank, gm_turn schema, Spark narrator
   |-- game: 15-state turn machine, night session, Demo Safe Mode
   |-- rules: pure deterministic engine (geometry, units, enemies, waves)
   |-- replay: highlights, 10 FPS proxy, reel render
   `-- db: SQLite (campaigns, units, turn log, api usage)
```

More: `docs/architecture/overview.md`.

## Requirements

- Windows 10 or 11 laptop
- A webcam pointed straight down at the desk, about 45 to 70 cm above it
- One A4 sheet for calibration
- Node.js 20+, Python 3.13, Git
- ffmpeg on PATH for recording and the replay reel (optional, the game runs without it)
- A Meta Model API key (optional, Demo Safe Mode plays a full night offline)

## Setup

```powershell
git clone https://github.com/EHIBE/DeskTop-Hanggang-Umaga.git
cd DeskTop-Hanggang-Umaga
npm --prefix app install
py -3.13 -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
npm --prefix app run dev
```

New here? The friendly walkthrough is in [docs/how-to-run.md](docs/how-to-run.md).

On first launch the app asks for your API key and stores it with Windows safeStorage. The key never reaches the renderer, the logs or the repo. Choose Play offline to use Demo Safe Mode instead.

## How to play

1. **Calibrate.** Lay the A4 sheet on the desk and tap its four corners. The desk becomes a top-down board.
2. **Summon.** Place one object at a time and say or type what it is. The first object is always the bahay kubo. Each object gets a unit card and a sprite.
3. **Claim.** Each player says "Ako si Migs, hawak ko ang Mug at Stapler", or taps names. Everyone answers whether tonight may be recorded.
4. **Survive eight turns.** Enemies spawn and show red arrows with their damage. Slide your objects within their move rings, give orders out loud ("Stapler, atake ang aswang!") or tap them, then say "Tapos na" or press End Turn. A tikbalang can shove a unit, so slide the object onto its shadow. A duwende can steal one, so take it off the table.
5. **Sunrise.** See the score and the Bayani ng Gabi, then make a replay reel of real hands with the pixel battle on top.

Rules in full: `docs/game/`.

## Results so far

Real numbers only, from real runs. Full log: `docs/eval.md`.

| Measure | Result |
|---|---|
| E7 Determinism (same board, same result) | 50 of 50 seeded boards identical, 100% (2026-10-29, rerun 2026-11-03) |
| Rules resolution speed | 1.1 ms median for 12 units and 8 enemies (target 50 ms) |
| Tracker speed | 31.9 ms median per update for 12 KCF trackers on a 1200x800 frame |
| Automated tests | 2,182 backend tests (end-to-end offline nights, server fuzz, rules invariants) and 84 renderer tests passing, plus typecheck, lint and format checks |
| E1 registration, E2 re-anchor, E3 Taglish orders, E4 GM validity, E5 sprites, E6 latency | Not run yet. They need live API runs and recorded nights |

## Cost per night

Estimated at about $0.49 for a typical night (8 objects, 2 players) and about $1.40 in the worst case, from list prices and token estimates in `docs/architecture/cost-and-budget.md`. A measured figure from `api_usage` will replace this after the playtest nights. The in-app meter stops all paid calls at $120.

## Privacy

| Data | Stays on the laptop | Sent to Meta |
|---|---|---|
| Full camera video | Yes | Never |
| Single desk frames and object crops | Yes | Yes, per call (Spark, SAM, Muse Image) |
| Microphone audio | Live only, never stored | Streamed to Voice Transcribe |
| GM narration input | Yes | Unit names, classes, HP and events. Players are sent as P1 to P4 |
| Replay proxy clip | Yes | Only with every player's consent, a 960 px highlight cut that expires in 24 h and is deleted after tracking |
| Database, sprites, recordings | Yes | Never |

Every response call sets `store: false`. Delete campaign removes its database rows, files, recordings and unshared sprites. More: `docs/engineering/security-and-privacy.md`.

## Known limits

- Summon is by typed name. Voice summon is not built.
- Kapre has no smoke effect, returning objects across nights and recaps are not built.
- The live shapes of some Meta responses (voice events, SAM video records) are coded from the docs and still need a recorded fixture.
- Tested on one Windows laptop. Lighting and camera height affect tracking.
- Taglish lines are waiting for review by Filipino playtesters.

More: `docs/product/scope-and-cuts.md` and `docs/delivery/risk-register.md`.

## Credits

- Font: Press Start 2P by The Press Start 2P Project Authors, SIL Open Font License 1.1 (`assets/fonts/OFL.txt`).
- Profanity lists: LDNOOBW, CC BY 4.0 (`backend/gm/data/ATTRIBUTION.md`).
- Sound effects: synthesized in code at runtime with WebAudio, no audio files.
- Folklore glossary and cultural care notes: `docs/glossary.md`, `docs/design/cultural-care.md`.

## License

Code: MIT, see `LICENSE`. Original assets made for DeskTop: CC BY-NC 4.0, see `assets/LICENSE-ASSETS.md`. Third-party assets keep their own licenses, listed in that file.
