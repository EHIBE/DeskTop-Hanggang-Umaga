---
title: WebSocket protocol
purpose: Local renderer to backend protocol, handshake, envelopes and every message type
read_when: [adding or changing a message, building lib/socket.ts or the /ws handler]
canonical_for: [local message types, envelope, handshake, event schema]
sources: [docs/DeskTop_Build_Guide.md#33-fastapi-frame-stream, docs/DeskTop_PRD.md#12-technical-architecture, docs/DeskTop_PRD.md#gm-contract]
status: active
last_verified: 2026-11-04
related: [docs/architecture/overview.md, docs/engineering/security-and-privacy.md, docs/design/hud-components.md]
---

# WebSocket protocol

The renderer and backend talk over one WebSocket at `ws://127.0.0.1:8765/ws`. Messages marked Established are built and tested. Only `uncertain.tap` and the envelope fields `seq` and `turn` are still Proposed. New messages go through the `desktop-add-ws-message` skill.

## Key facts

| Fact | Value |
|---|---|
| URL | `ws://127.0.0.1:<port>/ws`. Port is free-picked by Electron main on each backend start |
| Auth | Token sent as WebSocket subprotocols `["desktop", <DESKTOP_TOKEN>]` and compared with `hmac.compare_digest`. The server accepts with subprotocol `desktop`. Wrong or missing: close 1008 (HTTP 403 at handshake). The token is never in the URL, because uvicorn logs URLs |
| Origin | Must be in `DESKTOP_ALLOWED_ORIGINS` (dev server origin, or `file://` in a packaged build). `null` is added only when main sets `DESKTOP_PACKAGED=1` (ADR-0111). The token is always required |
| HTTP auth | `X-Desktop-Token` header on every route, 401 when missing or wrong |
| Encoding | JSON text frames with a `type` field |
| Frame rate | About 25 per second |
| Established | Server: `state`, `devices`, `campaigns`, `frame`, `notice`, `sprite`, `events`, `narration`, `caption`, `card`, `summon.result`, `cost` (dev). Renderer: `campaign.list`, `campaign.start`, `campaign.delete`, `devices.list`, `camera.select`, `calibrate.*`, `summon.*`, `unit.*`, `night.*`, `claim.*`, `intent.tap`, `chip.cancel`, `end_turn`, `demo_safe`, `demo_safe.sam`, `ptt`, `voice.mode`, `voice.retry`, `consent`, `effect.done`, `replay.request` (2026-10-29), `settings.get`, `settings.set`, `badge.pick`, `confirm.accept`, `confirm.cancel`, `map.get`, `crops.get`, `pause.quit`, `calibrate.back` (2026-11-04). Server adds `settings`, `map`, `crops`, `moment`, `recap` (2026-11-04). Types in `app/src/renderer/src/lib/types.ts`, Pydantic models in `backend/server.py` |
| Size limit | 16 KiB per renderer message. Larger or invalid messages get `notice` `cmd.unknown` |
| HTTP | `GET /health` returns `{"ok": true}` |

## Envelope

Every message is a JSON object with `type` plus fields. Proposed shared fields: `seq` (integer, server messages), `turn` (integer when relevant). Unknown types are ignored by the renderer and rejected by the backend.

## Server to renderer

| Type | Status | Fields | Purpose |
|---|---|---|---|
| `frame` | Established | `view` (raw or warped), `width` and `height` (source pixels, the JPEG is downscaled to 960 px wide, quality 70), `jpg`, `poses` | Desk feed and sprite positions |
| `state` | Established (M3 and M4 fields, plus `units`, `begin_block_key`, `awaiting_tap`) | `phase` (any AppPhase), `campaign`, `camera`, `calibrated`, `calibration_preview`, `play_w_cm`, `play_h_cm`, `demo_safe`, `demo_safe_sam`, `has_api_key`, `voice` (`status` off, connecting, listening or down, `mode` open or ptt, `ptt_down`), `resume_turn` (turn a saved night resumes at, or null), `recording` (bool), `consents` (player name to bool), `replay` (`status` idle, working, done or failed, `file`, `available`), `night` (turn, units with `status` tags `out_<n>`, `stolen_by:<enemy>`, `lost`, `returning`, enemies, chips, illegal units, kubo HP, `effects` with kind push or steal, unit id and target spot, `effect_seconds_left`), `score`, `settings`, `tts_available`, `progression`, `recap`, `pending_confirm`, `map` (see New post-freeze state fields) | Full snapshot on connect and after every handled message |
| `devices` | Established | `cameras` (index, width, height), `microphones` (index, name) | Device picker (FR-01) |
| `campaigns` | Established | `campaigns` (id, name, difficulty, nights_survived, created_at), newest first, 20 per page | Continue list (FR-05) |
| `events` | Established | `turn`, `events` (type, src, dst, dmg, edge, pos). Types include `push`, `thrown`, `steal`, `return` (pos is where the object goes back) and `escape` | Resolution events, then the next turn's spawn and intent events, as two messages |
| `caption` | Established | `turn_id`, `text`, `is_final`, `speaker` | Live transcript. Partials replace. A dropped turn ends with an empty final |
| `narration` | Established | `night`, `turn`, `phase` (night_start, resolution_then_telegraph, sunrise, defeat), `narration_tl`, `narration_en`, `mood`, `callouts`, `hint_tl`, `source` (spark or line_bank) | GM caption, sent in the background after claims, each resolved turn, sunrise or defeat. A newer request drops an older pending one |
| `summon.result` | Established | `unit_id`, `game_id`, `source` (spark or fallback), `spark_box` (warped pixels or null), `mask_hull`, `width`, `height` | After each summon, for the how-it-was-made panel |
| `chip` | Not used | none | Chips ride in `state.night.chips` with `source` (tap or voice) and `speaker` |
| `card` | Established | `unit` (id, unit_id, sam_id, name, class, hp, hp_max, atk, move, range, power_id, power_name_tl, card_text_tl, card_text_en, x_cm, y_cm, rerolls_left). `sprite_png` (base64 or null until the sprite is ready) | New or changed unit card |
| `sprite` | Established | `unit_id` (UUID), `sprite_png` (base64 48x48 PNG). `state.units[].sprite_png` carries it afterwards | Swap placeholder for real sprite. Pushed from the background job through a broadcast queue |
| `notice` | Established | `copy_key`, `params` | Banner or prompt by copy key (never raw text) |
| `settings` | Established | `values` (the nine settings), `tts_available` (always false) | Reply to `settings.get` and `settings.set` |
| `map` | Established | `png` (base64 PNG, play area aspect, long side 1024) | Reply to `map.get`, and pushed when a generated barrio map finishes |
| `crops` | Established | `crops` (db `unit_id` to base64 PNG, 128 px long side) | Reply to `crops.get`, for the show real objects setting |
| `moment` | Established | `moment`, `text_tl`, `text_en`, `mood`, `unit_id` (game id or null) | Line bank caption for `kapre_smoke_telegraph`, `kapre_smoke_hit`, `unit_lost`, `unit_returned`, `badge_earned`, `scar_gained`, `object_recognized`. Never Spark |
| `recap` | Established | `night`, `text_tl`, `text_en`, `mood`, `source` (spark, line_bank or glimmer) | Reply to `campaign.start` with an existing id when a Kagabi recap is saved. Also in `state.recap` until the next night starts |
| `cost` | Established, dev only (`DESKTOP_DEV=1`) | `spent_usd` (decimal string, 6 places), `warn`, `stopped` | Credit meter. Sent on connect and after every handled message |

## Renderer to server

| Type | Status | Fields | Valid in |
|---|---|---|---|
| `calibrate.corners` | Established | `corners` (4 points TL, TR, BR, BL in raw camera pixels), `play_w_cm`, `play_h_cm` (30 to 120) | CALIBRATE with a camera open |
| `calibrate.done` | Established | none. Saves the empty-desk baseline and the calibration row | CALIBRATE with corners set |
| `calibrate.restart` | Established | none | Any phase with a campaign |
| `campaign.start` | Established | `campaign_id` (UUID) or `new` with `name` (1 to 40) and optional `difficulty`. A missing difficulty uses the `difficulty` setting (easy is madali, normal, hard is mahirap) | Start |
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
| `consent` | Established | `player_name`, `agree` (bool). Recording starts after claims only when every claimed player agreed | VOICE_CLAIM |
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
| `replay.request` | Established | none. Builds the reel in the background. Notices `replay.making`, `replay.done`, `replay.failed`, `replay.none` | SUNRISE or DEFEAT after a consented recording |
| `campaign.delete` | Established | `campaign_id`. Replies with `campaigns` and notice `delete.done`, or `delete.failed`. Also removes the generated map | START |
| `settings.get` | Established | none. Replies `settings` | Any |
| `settings.set` | Established | `key` (camera_device, mic_device, caption_language, difficulty, replay_enabled, tts_enabled, show_real_objects, strict_ownership, generated_map), `value` (bool, int or string, checked per key). Replies `settings`. Bad key or value: notice `settings.invalid` | Any. `camera_device` also needs no active night |
| `badge.pick` | Established | `unit_id` (game id), `badge` (hp or cooldown). Must be one of that unit's offers. Applied and saved | SUNRISE |
| `confirm.accept` | Established | `confirm_id` (UUID from `state.pending_confirm`). Adds the held voice order | PLAYER_PHASE |
| `confirm.cancel` | Established | `confirm_id`. Drops the held order | PLAYER_PHASE |
| `map.get` | Established | none. Replies `map`, or notice `map.none` | Any |
| `crops.get` | Established | none. Replies `crops` for the current night's units | Any |
| `pause.quit` | Established | none. Ends the night to START. The autosave stays, so Continue restores it | PAUSED |
| `calibrate.back` | Established | none. Back to START without a campaign | CALIBRATE |

The backend validates every message with a Pydantic model (`extra="forbid"`), checks the current state, and checks every ID against live state. Invalid messages get a `notice` and are logged.

## New post-freeze state fields

All new fields ride in `state`. Field names are exact.

| Field | Shape | Notes |
|---|---|---|
| `settings` | `{camera_device: int, mic_device: string, caption_language: "tl" or "en", difficulty: "easy", "normal" or "hard", replay_enabled: bool, tts_enabled: bool, show_real_objects: bool, strict_ownership: bool, generated_map: bool}` | Defaults 0, "default", "tl", "normal", true, false, true, false, false. `mic_device` is "default" or a microphone index as a string. `tts_enabled` is always false in state because there is no TTS engine. `replay_enabled` false turns off recording, the consent prompt and Make Replay (notice `replay.off`). `show_real_objects` true means show the camera crop (`crops.get`) instead of the sprite |
| `tts_available` | bool | Always false |
| `progression` | `{barrio_level: 0 to 5, nights_survived: int, badge_offers: [{unit_id, choices: ["hp" or "cooldown"]}]}` or null | Offers appear after a sunrise and clear per unit when `badge.pick` succeeds. They are not saved, so leaving the sunrise screen drops unpicked offers |
| `recap` | `{night, text_tl, text_en, mood, source}` or null | Set by Continue when a recap is saved, cleared when the next night starts (claims done) |
| `pending_confirm` | `{confirm_id, unit_id, unit_name, owner, speaker, action, target_id, text_tl, text_en, seconds_left}` or null | A held voice order when `strict_ownership` is on and a known player spoke for another player's unit. Expires after 20 s. Answer with `confirm.accept` or `confirm.cancel` |
| `map` | `{enabled: bool, ready: bool, working: bool}` | `ready` means a cached map exists and the setting is on. Fetch it with `map.get` |
| `units[]` (and `card.unit`) | adds `returning: bool`, `badges: ["hp" or "cooldown"]`, `scars: int` | `returning` is true when the object was matched to a unit from an earlier night. Rerolls are refused for it |
| `night.units[]` | adds `badges`, `scars`, `cooldown_cut: int`, `smoked: bool` | `status` also carries `off_desk` when the centroid is outside the play area. HP max already includes badges and scars |
| `night.smoke` | `[{source_id, x_cm, y_cm, radius_cm}]` | Kapre smoke clouds for the current turn, in board cm. Rebuilt from the saved turn on restore |
| `summon.result` | adds `returning: bool` | |

New notice keys the renderer must carry copy for: `settings.invalid`, `replay.off`, `map.none`, `unit.lost` (param `unit`), `unit.found` (param `unit`).

Order flow: a voice order that the grammar cannot parse goes to a Spark fallback in the background (6 s timeout, skipped in Demo Safe Mode and at the cost hard stop). A fallback result of end turn is ignored on purpose. Strict ownership uses the speaker name only when diarization mapped the voice to a claimed player.

## Event schema (inside `events`)

| Field | Type | Notes |
|---|---|---|
| `type` | enum | attack, dodge, spawn, intent, heal, power, shield, down, push, thrown, steal, return, escape, split, reform, kubo_hit, defeat_enemy, smoke, smoke_cleared, lost, found, win, lose |
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
