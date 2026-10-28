---
title: WebSocket protocol
purpose: Local renderer to backend protocol, handshake, envelopes and every message type
read_when: [adding or changing a message, building lib/socket.ts or the /ws handler]
canonical_for: [local message types, envelope, handshake, event schema]
sources: [docs/DeskTop_Build_Guide.md#33-fastapi-frame-stream, docs/DeskTop_PRD.md#12-technical-architecture, docs/DeskTop_PRD.md#gm-contract]
status: active
last_verified: 2026-10-28
related: [docs/architecture/overview.md, docs/engineering/security-and-privacy.md, docs/design/hud-components.md]
---

# WebSocket protocol

The renderer and backend talk over one WebSocket at `ws://127.0.0.1:8765/ws`. Only the `frame` message is established by the Build Guide. Every other message here is Proposed and must be confirmed when first built, using the `desktop-add-ws-message` skill.

## Key facts

| Fact | Value |
|---|---|
| URL | `ws://127.0.0.1:<port>/ws`. Port is free-picked by Electron main on each backend start |
| Auth | Token sent as WebSocket subprotocols `["desktop", <DESKTOP_TOKEN>]` and compared with `hmac.compare_digest`. The server accepts with subprotocol `desktop`. Wrong or missing: close 1008 (HTTP 403 at handshake). The token is never in the URL, because uvicorn logs URLs |
| Origin | Must be in `DESKTOP_ALLOWED_ORIGINS` (dev server origin, or `file://` and `null` in a packaged build) |
| HTTP auth | `X-Desktop-Token` header on every route, 401 when missing or wrong |
| Encoding | JSON text frames with a `type` field |
| Frame rate | About 25 per second |
| Established | Server: `state`, `devices`, `campaigns`, `frame`, `notice`. Renderer: `campaign.list`, `campaign.start`, `devices.list`, `camera.select`, `calibrate.corners`, `calibrate.done`, `calibrate.restart`, `demo_safe` (2026-10-28). Types in `app/src/renderer/src/lib/types.ts`, Pydantic models in `backend/server.py` |
| Size limit | 16 KiB per renderer message. Larger or invalid messages get `notice` `cmd.unknown` |
| HTTP | `GET /health` returns `{"ok": true}` |

## Envelope

Every message is a JSON object with `type` plus fields. Proposed shared fields: `seq` (integer, server messages), `turn` (integer when relevant). Unknown types are ignored by the renderer and rejected by the backend.

## Server to renderer

| Type | Status | Fields | Purpose |
|---|---|---|---|
| `frame` | Established | `view` (raw or warped), `width` and `height` (source pixels, the JPEG is downscaled to 960 px wide, quality 70), `jpg`, `poses` | Desk feed and sprite positions |
| `state` | Established (M3 fields) | `phase` (START, CALIBRATE, SUMMON so far), `campaign`, `camera`, `calibrated`, `calibration_preview`, `play_w_cm`, `play_h_cm`, `demo_safe`, `has_api_key`. Night fields (`turn`, `night`, `kubo`, `units`, `enemies`, `flags`) arrive in M7 | Full snapshot on connect and after every handled message |
| `devices` | Established | `cameras` (index, width, height), `microphones` (index, name) | Device picker (FR-01) |
| `campaigns` | Established | `campaigns` (id, name, difficulty, nights_survived, created_at), newest first, 20 per page | Continue list (FR-05) |
| `events` | Proposed | `events` (ordered list) | Resolution events for animations |
| `caption` | Proposed | `turn_id`, `text`, `is_final`, `speaker` | Live transcript (partials replace) |
| `narration` | Proposed | `narration_tl`, `narration_en`, `mood`, `callouts`, `hint_tl`, `source` (spark or line_bank) | GM caption |
| `chip` | Proposed | `chip_id`, `unit_id`, `action`, `target_id`, `speaker`, `status` | Order chip add, update, remove |
| `card` | Proposed | `unit` (card fields), `sprite_url` or placeholder class | New unit card |
| `sprite` | Proposed | `unit_id`, `sprite_url` | Swap placeholder for real sprite |
| `notice` | Established | `copy_key`, `params` | Banner or prompt by copy key (never raw text) |
| `cost` | Proposed, dev only | `spent_usd`, `warn`, `stopped` | Credit meter |

## Renderer to server

| Type | Status | Fields | Valid in |
|---|---|---|---|
| `calibrate.corners` | Established | `corners` (4 points TL, TR, BR, BL in raw camera pixels), `play_w_cm`, `play_h_cm` (30 to 120) | CALIBRATE with a camera open |
| `calibrate.done` | Established | none. Saves the empty-desk baseline and the calibration row | CALIBRATE with corners set |
| `calibrate.restart` | Established | none | Any phase with a campaign |
| `campaign.start` | Established | `campaign_id` (UUID) or `new` with `name` (1 to 40), `difficulty` | Start |
| `campaign.list` | Established | none | Any |
| `devices.list` | Established | none | Any |
| `camera.select` | Established | `index` (0 to 5). On Continue, compares the stored baseline and skips calibration when the camera has not moved | Any phase with a campaign |
| `summon.name` | Proposed | `name` (typed) | SUMMON |
| `summon.tap` | Proposed | `point` | SUMMON (unclear object) |
| `night.begin` | Proposed | none | SUMMON with valid roster |
| `claim.tap` | Proposed | `player_name`, `unit_ids` | VOICE_CLAIM |
| `consent` | Proposed | `player_id`, `agree` | Before Start Night |
| `intent.tap` | Proposed | `unit_id`, `action`, `target_id` | PLAYER_PHASE |
| `chip.cancel` | Proposed | `chip_id` | PLAYER_PHASE |
| `end_turn` | Proposed | none | PLAYER_PHASE |
| `uncertain.tap` | Proposed | `unit_id`, `point` | VALIDATE or PLAYER_PHASE |
| `ptt` | Proposed | `down` (bool) | PLAYER_PHASE |
| `pause` / `resume` | Proposed | none | Any night state |
| `demo_safe` | Established | `on` (bool). Persisted in `settings` | Any |
| `replay.request` | Proposed | none | SUNRISE with consent |
| `campaign.delete` | Proposed | `campaign_id` | Campaign menu |

The backend validates every message with a Pydantic model (`extra="forbid"`), checks the current state, and checks every ID against live state. Invalid messages get a `notice` and are logged.

## Event schema (inside `events`)

| Field | Type | Notes |
|---|---|---|
| `type` | enum | attack, dodge, spawn, intent, heal, power, shield, down, push, steal, return, escape, split, reform, kubo_hit, win, lose |
| `src` | string or null | Unit or enemy ID |
| `dst` | string or null | Unit or enemy ID |
| `dmg` | integer or null | Damage after shields |
| `edge` | string or null | Spawn edge |
| `pos` | object or null | Target position in cm for push and return |

The same events feed the GM input (`ai-contracts.md`) and turn_log.

## Message rules

- Never send the API key or token in any message body.
- Never send raw model output. Send validated fields only.
- Text for players goes as copy keys plus params, except transcripts and validated narration.
