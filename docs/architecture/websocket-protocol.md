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
| URL | `ws://127.0.0.1:8765/ws?token=<DESKTOP_TOKEN>` |
| Auth | Token compared with `hmac.compare_digest`. Wrong or missing: close 1008 |
| Origin | Checked against the app origin |
| Encoding | JSON text frames with a `type` field |
| Frame rate | About 25 per second |
| Established | `frame` |
| HTTP | `GET /health` returns `{"ok": true}` |

## Envelope

Every message is a JSON object with `type` plus fields. Proposed shared fields: `seq` (integer, server messages), `turn` (integer when relevant). Unknown types are ignored by the renderer and rejected by the backend.

## Server to renderer

| Type | Status | Fields | Purpose |
|---|---|---|---|
| `frame` | Established | `jpg` (base64 JPEG, 960 px wide, quality 70), `poses` | Desk feed and sprite positions |
| `state` | Proposed | `phase`, `turn`, `night`, `kubo`, `units`, `enemies`, `flags`, `demo_safe` | Full game snapshot on connect and each phase change |
| `events` | Proposed | `events` (ordered list) | Resolution events for animations |
| `caption` | Proposed | `turn_id`, `text`, `is_final`, `speaker` | Live transcript (partials replace) |
| `narration` | Proposed | `narration_tl`, `narration_en`, `mood`, `callouts`, `hint_tl`, `source` (spark or line_bank) | GM caption |
| `chip` | Proposed | `chip_id`, `unit_id`, `action`, `target_id`, `speaker`, `status` | Order chip add, update, remove |
| `card` | Proposed | `unit` (card fields), `sprite_url` or placeholder class | New unit card |
| `sprite` | Proposed | `unit_id`, `sprite_url` | Swap placeholder for real sprite |
| `notice` | Proposed | `copy_key`, `params` | Banner or prompt by copy key (never raw text) |
| `cost` | Proposed, dev only | `spent_usd`, `warn`, `stopped` | Credit meter |

## Renderer to server

| Type | Status | Fields | Valid in |
|---|---|---|---|
| `calibrate.corners` | Proposed | `corners` (4 points), `play_w_cm`, `play_h_cm` | CALIBRATE |
| `campaign.start` | Proposed | `campaign_id` or `new` with `name`, `difficulty` | Start |
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
| `demo_safe` | Proposed | `on` (bool) | Start |
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
