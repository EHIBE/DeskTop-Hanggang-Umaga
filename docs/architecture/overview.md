---
title: Architecture overview
purpose: Components, processes, data flow, trust boundaries and key technical decisions
read_when: [starting any engineering work, placing a new responsibility]
canonical_for: [component map, process model, data flow, trust boundaries]
sources: [docs/DeskTop_PRD.md#12-technical-architecture, docs/DeskTop_PRD.md#system-at-a-glance]
status: active
last_verified: 2026-11-04
related: [docs/decisions/ADR-0111-packaged-build-and-origin.md, docs/decisions/ADR-0113-post-freeze-cut-features.md, docs/architecture/backend-modules.md, docs/architecture/frontend-modules.md, docs/architecture/websocket-protocol.md, docs/engineering/security-and-privacy.md]
---

# Architecture overview

DeskTop is an Electron app with a React renderer and a Python FastAPI backend that runs on 127.0.0.1 as a child process. The backend owns the camera, mic, rules, database and every Meta API call.

## Key facts

| Fact | Value |
|---|---|
| Processes | Electron main, Electron renderer, Python backend (uvicorn) |
| Local transport | WebSocket `/ws` plus HTTP `/health` on 127.0.0.1, on a free port Electron picks each launch (`findFreePort` in `app/src/main/backend.ts`). 8765 is only the default for a manual run (`backend/config.py`) |
| Auth | 64 hex token regenerated each launch. HTTP header `x-desktop-token` (401 on mismatch). WS Origin allowlist plus subprotocol `desktop, <token>` (close 1008). `null` origin only when `DESKTOP_PACKAGED=1` (ADR-0111) |
| External | api.meta.ai/v1 (Responses, Files), wss://api.meta.ai/v1/asr/realtime. Optional local Muse Glimmer on a loopback URL from `DESKTOP_GLIMMER_URL`, read only from `backend/.env` in dev because `PASSTHROUGH_ENV` does not forward it |
| Database | SQLite in the Electron user data folder (`%APPDATA%\DeskTop\`) |
| Authoritative logic | `backend/rules` (pure Python) |
| Current code | M0 to M11, Phases 12 to 15, the UI redesign and the ADR-0113 post-freeze features, 16 states, schema v3. Packaged zip per ADR-0111. History: `docs/delivery/build-log.md` |

## Components

```mermaid
flowchart TB
  subgraph Electron
    MAIN[Main process: spawns backend on a free port, safeStorage key, window]
    REN[Renderer: React + TS + Tailwind, canvas HUD]
  end
  subgraph Backend [FastAPI on 127.0.0.1]
    CAP[Capture: OpenCV camera, sounddevice mic]
    WARP[Homography warp + px per cm]
    TRK[Tracker: KCF per object at 640 px]
    REC[Recorder: ffmpeg H.264 MP4]
    PARSE[Command grammar]
    RULES[Rules engine: pure Python, shapely]
    SM[Turn state machine]
    CLIENT[Meta client: OpenAI SDK + websockets, retries, breaker, cost meter]
    DB[(SQLite)]
  end
  MAIN -- spawn + env key + token --> Backend
  REN <-- WS: frames JPEG, poses, events --> SM
  CAP --> WARP --> TRK --> SM
  WARP --> REC
  CAP -- PCM 24 kHz --> CLIENT
  SM --> RULES
  SM --> PARSE
  SM --> DB
  CLIENT --> META[(api.meta.ai/v1)]
```

## Data flow per phase

| Phase | Flow |
|---|---|
| Calibration | Camera frame, optional SAM concept call, homography saved |
| Summon | Voice (endpointing) gives the name. Warped snapshot plus name plus known boxes to Spark. Box to SAM with all known boxes. Rules clamp. Card to renderer. Background sprite job to Muse Image |
| Player phase | Camera to tracker at 10 Hz+, poses to renderer at about 25 Hz. Mic to voice (diarization). Transcripts to grammar. Intents to chips |
| End Turn | Snapshot, one SAM call, reconcile, Lost detection (`rules/lost.py`), validate, `resolve_turn`, events to renderer, GM narration in background, autosave |
| Sunrise | Badge offer and scars (`rules/progression.py`). With consent: highlights, proxy, upload, SAM video, delete upload, local render. The Kagabi recap (Glimmer, then Spark, then the line bank, `gm/recap.py`) shows at the start of the next night |

## Trust boundaries

| Boundary | Rule |
|---|---|
| Renderer to backend | Untrusted input. Token on every request, Pydantic validation, state checks |
| Backend to Meta | Key in env only. Standard mode. Only frames, crops, live audio, consented proxy leave the laptop |
| Meta to backend | Untrusted output. Strict schemas, enum IDs from live state, clamps, repair then fallback |
| Main to renderer | Preload exposes `getConfig`, `getKeyStatus`, `saveKey` and `showReel` only (ADR-0103) |

## Key decisions

| Decision | ADR |
|---|---|
| Turn-based | ADR-0001 |
| Hybrid tracking, Spark plus SAM box prompts | ADR-0002 |
| Rules engine authoritative | ADR-0003 |
| SQLite | ADR-0004 |
| Chroma key sprites | ADR-0005 |
| Local-first | ADR-0006 |
| Voice with fallbacks | ADR-0007 |
| Backend owns devices | ADR-0008 |
| ffmpeg H.264 | ADR-0009 |
| OpenAI SDK for Meta | ADR-0010 |
| Packaged zip, fuses, `null` origin only when packaged | ADR-0111 |
| Finalization scope | ADR-0112 |
| Post-freeze features and their defaults | ADR-0113 |

## Runtime data (not in the repo)

SQLite database, sprites made during play and recordings live in `%APPDATA%\DeskTop\`. Electron main passes this path to the backend at spawn. Delete campaign removes only files under this root (FR-52).
