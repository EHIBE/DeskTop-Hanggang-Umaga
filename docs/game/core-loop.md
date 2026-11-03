---
title: Core loop
purpose: The play loop, session shape and every player-facing flow from launch to resume
read_when: [designing any screen or phase, explaining how a night plays]
canonical_for: [core loop, session numbers, flows F1 to F10 summary]
sources: [docs/DeskTop_PRD.md#8-game-design-specification, docs/DeskTop_PRD.md#7-solution-overview-and-key-flows]
status: active
last_verified: 2026-11-04
related: [docs/game/state-machine.md, docs/game/combat-math.md, docs/design/screens.md]
---

# Core loop

Players place objects, name them, then survive eight telegraphed turns of folklore attacks by moving real objects and giving spoken orders. No combat randomness exists, so the same inputs give the same outcome.

## Key facts

| Item | Value |
|---|---|
| Loop | Place, name, night falls, see threats, talk, move by hand, order, End Turn, watch, repeat 8 times, sunrise, replay |
| Night length | 8 turns |
| Target turn time | 90 to 120 s |
| Session | About 3 min setup plus 12 to 18 min night |
| Players | 1 to 4, co-op |
| Units | 1 kubo plus 2 to 11 more, 12 objects max (SAM limit is 16, margin for safety) |
| Randomness | None in combat. Wave order fixed per difficulty |

## Flows

Step-by-step tables with models called and data written: PRD section 7. This is the summary.

| Flow | Trigger | What happens | Models |
|---|---|---|---|
| F1 First launch and calibration | App opens | Backend spawns, key stored with safeStorage, camera and mic picked, A4 corners auto-detected or tapped, homography and px per cm saved, play area dragged (default 60 x 40 cm), baseline frame stored | SAM concept prompt "white paper" (optional) |
| F2 Set the table | New Campaign or Continue | Difficulty picked, camera-moved check, barrio tiles at 35% opacity over the feed. Saying "Tabi tabi po" skips the turn 2 duwende | Voice (summon session) |
| F3 Summon | Object placed and named | Snapshot 1 s after the hand leaves. Spark returns box, label, card. Rules clamp. SAM masks every object. Card with placeholder in about 8 s. Sprite generates in background. Begin Night needs exactly one kubo and 2+ other units, max 12 | Voice, Spark (medium), SAM, Muse Image |
| F4 Voice claim | Roster valid | Summon session closes. Night session opens in DIARIZATION with keywords. "Ako si [name], hawak ko ang [units]" maps labels to players. Skip lets players tap names | Voice |
| F5 One turn | Turn start | Spawn and telegraph, narration, planning and moving, End Turn snapshot, validate, player resolution, enemy attack, physical effects, resolution narration, check and autosave | Spark (low), SAM |
| F6 Enemy phase | Spawn step | Spawn at listed edges, pick target by AI rule, move toward it stopping at range, draw arrow with damage number | None |
| F7 Sunrise | Turn 8 survived | Dawn over 3 s, score, Bayani ng Gabi, recap line, Replay if consent | Spark (recap), SAM video |
| F8 Replay | Replay tapped | Highlights from turn_log, 10 FPS proxy, upload with 24 h expiry, SAM video tracking, delete upload, render 1080p reel locally, 60 s max | SAM, Files API |
| F9 Resume next night | Continue | Load campaign, match returning objects locally, reuse sprites, show "Kagabi..." recap | Local Glimmer, Spark or line bank |
| F10 Error recovery | Failure | Retries, circuit breaker, camera-moved pause, backend restart from autosave | None |

Narration for turn N resolution and turn N+1 telegraph come back in one call.

## Fallbacks in flow

- Spark cannot tell which object is new: "Alin ang bago? I-tap mo." and the player taps it.
- Voice claim fails: Skip, players tap name chips and drag units to them.
- Loss path: kubo HP 0 or every non-kubo unit down. "Nasira ang kubo... Subukan ulit bukas ng gabi."

## Design intent

| Goal | How the loop serves it |
|---|---|
| PG-1 setup under 5 min | One A4 sheet, one object at a time, placeholder first |
| PG-2 never wait on AI | Model calls only at turn boundaries, narration never blocks |
| PG-3 explainable | Telegraphed intents, fixed tables, no dice |
| PG-4 feels Filipino | Folklore, barrio, Taglish copy, "Tabi tabi po" |
| PG-5 shareable | Replay reel of real hands |
| JS-12 learn by playing | Turn 1 is a single aswang |
