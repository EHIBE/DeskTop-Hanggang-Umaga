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
| Established | Server: `state`, `devices`, `campaigns`, `frame`, `notice`, `sprite`, `events`, `narration`, `caption`, `cost` (dev). Renderer: `campaign.list`, `campaign.start`, `campaign.delete`, `devices.list`, `camera.select`, `calibrate.*`, `summon.*`, `unit.*`, `night.*`, `claim.*`, `intent.tap`, `chip.cancel`, `end_turn`, `demo_safe`, `demo_safe.sam`, `ptt`, `voice.mode`, `voice.retry` (2026-10-28). Types in `app/src/renderer/src/lib/types.ts`, Pydantic models in `backend/server.py` |
| Size limit | 16 KiB per renderer message. Larger or invalid messages get `notice` `cmd.unknown` |
| HTTP | `GET /health` returns `{"ok": true}` |

## Envelope

Every message is a JSON object with `type` plus fields. Proposed shared fields: `seq` (integer, server messages), `turn` (integer when relevant). Unknown types are ignored by the renderer and rejected by the backend.

## Server to renderer

| Type | Status | Fields | Purpose |
|---|---|---|---|
| `frame` | Established | `view` (raw or warped), `width` and `height` (source pixels, the JPEG is downscaled to 960 px wide, quality 70), `jpg`, `poses` | Desk feed and sprite positions |
| `state` | Established (M3 and M4 fields, plus `units`, `begin_block_key`, `awaiting_tap`) | `phase` (any AppPhase), `campaign`, `camera`, `calibrated`, `calibration_preview`, `play_w_cm`, `play_h_cm`, `demo_safe`, `demo_safe_sam`, `has_api_key`, `voice` (`status` off, connecting, listening or down, `mode` open or ptt, `ptt_down`), `resume_turn` (turn a saved night resumes at, or null), `night` (turn, units with `status` tags `out_<n>`, `stolen_by:<enemy>`, `lost`, `returning`, enemies, chips, illegal units, kubo HP, `effects` with kind push or steal, unit id and target spot, `effect_seconds_left`), `score` | Full snapshot on connect and after every handled message |
| `devices` | Established | `cameras` (index, width, height), `microphones` (index, name) | Device picker (FR-01) |
| `campaigns` | Established | `campaigns` (id, name, difficulty, nights_survived, created_at), newest first, 20 per page | Continue list (FR-05) |
| `events` | Established | `turn`, `events` (type, src, dst, dmg, edge, pos). Types include `push`, `thrown`, `steal`, `return` (pos is where the object goes back) and `escape` | Resolution events, then the next turn's spawn and intent events, as two messages |
| `caption` | Established | `turn_id`, `text`, `is_final`, `speaker` | Live transcript. Partials replace. A dropped turn ends with an empty final |
| `narration` | Established | `night`, `turn`, `phase` (night_start, resolution_then_telegraph, sunrise, defeat), `narration_tl`, `narration_en`, `mood`, `callouts`, `hint_tl`, `source` (spark or line_bank) | GM caption, sent in the background after claims, each resolved turn, sunrise or defeat. A newer request drops an older pending one |
| `chip` | Not used | none | Chips ride in `state.night.chips` with `source` (tap or voice) and `speaker` |
| `card` | Established | `unit` (id, unit_id, sam_id, name, class, hp, hp_max, atk, move, range, power_id, power_name_tl, card_text_tl, card_text_en, x_cm, y_cm, rerolls_left). `sprite_url` arrives in M5 | New or changed unit card |
| `sprite` | Established | `unit_id` (UUID), `sprite_png` (base64 48x48 PNG). `state.units[].sprite_png` carries it afterwards | Swap placeholder for real sprite. Pushed from the background job through a broadcast queue |
| `notice` | Established | `copy_key`, `params` | Banner or prompt by copy key (never raw text) |
| `cost` | Established, dev only (`DESKTOP_DEV=1`) | `spent_usd` (decimal string, 6 places), `warn`, `stopped` | Credit meter. Sent on connect and after every handled message |

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
| `summon.name` | Established | `name` (1 to 40) | SUMMON. Replies `card`, or `notice` `summon.which` with `state.awaiting_tap` true |
| `summon.tap` | Established | `point` (warped pixels) | SUMMON while `awaiting_tap` |
| `unit.reroll` | Established | `unit_id` (UUID) | SUMMON, one per unit |
| `unit.rename` | Established | `unit_id`, `name` (1 to 40, profanity filtered) | SUMMON |
| `night.begin` | Established | none | SUMMON with a valid roster |
| `claim.tap` | Established | `player_name` (1 to 24, filtered), `unit_ids` (game ids, max 12) | VOICE_CLAIM, max 4 players |
| `claim.done` | Established | none (Done and Skip) | VOICE_CLAIM |
| `night.next` | Established | none | SUNRISE or DEFEAT, starts a fresh summon |
| `night.quit` | Established | none | SUNRISE or DEFEAT, back to START |
| `consent` | Proposed | `player_id`, `agree` | Before Start Night |
| `intent.tap` | Established | `unit_id` (game id), `action` (attack, power, heal), `target_id` (game id or null). Validated by `rules.resolve.intent_error` | PLAYER_PHASE |
| `chip.cancel` | Established | `chip_id` | PLAYER_PHASE |
| `end_turn` | Established | none. Re-anchor, validate, resolve, autosave | PLAYER_PHASE |
| `uncertain.tap` | Proposed | `unit_id`, `point` | VALIDATE or PLAYER_PHASE |
| `ptt` | Established | `down` (bool). Only in push-to-talk mode, else `cmd.unknown`. A release outside it is ignored | Any |
| `voice.mode` | Established | `mode` (open or ptt) | Any |
| `voice.retry` | Established | none. Restarts the voice session | Active night or PAUSED |
| `night.pause` | Established | none | PLAYER_PHASE to PAUSED |
| `night.resume` | Established | `force` (bool, default false). Without force a still-moved camera answers `cam.moved` and stays PAUSED | PAUSED |
| `effect.done` | Established | none. Players moved or removed the object | PHYSICAL_EFFECTS |
| `demo_safe` | Established | `on` (bool). Persisted in `settings` | Any |
| `demo_safe.sam` | Established | `on` (bool). SAM re-anchor inside Demo Safe Mode, on by default. Persisted in `settings` | Any |
| `replay.request` | Proposed | none | SUNRISE with consent |
| `campaign.delete` | Established | `campaign_id`. Replies with `campaigns` and notice `delete.done`, or `delete.failed` | START |

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
