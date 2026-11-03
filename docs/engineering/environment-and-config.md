---
title: Environment and config
purpose: Environment variables, config constants and where runtime paths come from
read_when: [adding a config key or env var, wiring backend spawn]
canonical_for: [env var list, config.py groups, runtime paths]
sources: [backend/.env.example, docs/DeskTop_Build_Guide.md#32-spawn-the-backend-from-electron-main, docs/DeskTop_PRD.md#12-technical-architecture]
status: active
last_verified: 2026-10-28
related: [docs/game/balance-and-tuning.md, docs/engineering/security-and-privacy.md, docs/engineering/setup-windows.md]
---

# Environment and config

Secrets and per-launch values arrive as environment variables from Electron main. Everything else is a typed constant in `backend/config.py`.

## Key facts

| Fact | Value |
|---|---|
| Template | `backend/.env.example` (placeholders only) |
| Dev secrets | `backend/.env` (git-ignored, never read by agents) |
| Constants | `backend/config.py` (built. `load_settings(env)` returns a frozen `AppSettings` whose repr hides the token and key) |
| Tunables list | `docs/game/balance-and-tuning.md` |

## Environment variables

| Name | Set by | Purpose | In .env.example |
|---|---|---|---|
| `MODEL_API_KEY` | Electron main from safeStorage (dev: `backend/.env`) | Meta API key | Yes, empty |
| `DESKTOP_TOKEN` | Electron main, random per launch | Local auth token. Backend refuses to start without one of 32 or more characters (ADR-0012) | Yes, empty |
| `DESKTOP_DATA_DIR` | Electron main (`app.getPath('userData')`) | Runtime data root. Unset means `%APPDATA%\DeskTop` | Yes, empty |
| `DESKTOP_PORT` | Electron main (free loopback port per start) | Backend port, default 8765 for manual runs. Blank means default | Yes, 8765 |
| `DESKTOP_ALLOWED_ORIGINS` | Electron main | Comma list of WebSocket origins the backend accepts | No (set by main) |
| `DESKTOP_PACKAGED` | Electron main when `app.isPackaged` | Adds the `null` origin of a `file://` page to the WebSocket allow-list. The token is still required (ADR-0111) | No (set by main) |
| `DESKTOP_DEV` | Electron main in dev | Enables `.env` loading and the dev cost meter messages | No (set by main) |
| `DESKTOP_FFMPEG` | Optional, user | Path to ffmpeg.exe when it is not on PATH. Used by the recorder and the replay. Main passes it through to the spawned backend | Yes, empty |

All four names are Established and listed in `backend/.env.example` with placeholders.

## config.py groups

| Group | Examples |
|---|---|
| Geometry | `PX_PER_CM = 20`, play area 60 x 40 cm, A4 21.0 x 29.7 cm, move and range cm |
| Thresholds | SAM confidence 0.5, IoU 0.3, histogram 0.35, recovery 15 cm |
| Timeouts | Spark 20 s, SAM image 10 s, SAM video 120 s, Muse Image 45 s, Files 60 s |
| Retries | 2, backoff 0.5 s and 1 s, jitter 250 ms, breaker 3 failures for 120 s |
| Prices | Unit price table (`architecture/cost-and-budget.md`) as Decimal |
| Budget | Warn 90, stop 120 |
| Models | Model ID strings, base URL, realtime URL |
| Versions | `PALETTE_VERSION`, `PROMPT_VERSION` |

## Rules

- No secret in `config.py`.
- No default that weakens security (debug off, docs off by default).
- Load env once at startup and pass values in through injection.
