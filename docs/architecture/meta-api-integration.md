---
title: Meta API integration
purpose: Every Meta model call with exact parameters, limits, frequency, cost and items still to verify
read_when: [adding or changing any call in meta_client.py, vision, voice, gm or replay]
canonical_for: [per-call parameters, model IDs, endpoints, model limits, SAM prompt format, verify list]
sources: [docs/DeskTop_PRD.md#per-model-integration-table, docs/DeskTop_PRD.md#sam-usage-spec, docs/DeskTop_Build_Guide.md#phase-1-api-smoke-tests-oct-28-15-h]
status: active
last_verified: 2026-10-28
related: [docs/architecture/cost-and-budget.md, docs/architecture/reliability-and-fallbacks.md, docs/decisions/ADR-0010-openai-sdk-for-meta.md]
---

# Meta API integration

Four Meta models plus the Files API, all called from `backend/meta_client.py` in Standard mode. Model limits and prices were verified on dev.meta.ai on 2026-10-25 (PRD), and items marked Verify still need a live check.

## Key facts

| Fact | Value |
|---|---|
| Base URL | `https://api.meta.ai/v1` (OpenAI SDK `base_url`) |
| Realtime voice | `wss://api.meta.ai/v1/asr/realtime` |
| Auth | `MODEL_API_KEY` from env, set by Electron main at spawn |
| Mode | Standard only. Never Contributor mode (NFR-23) |
| Model IDs | `muse-spark-1.3`, `sam-3.1`, `muse-image-1.0`, `muse-voice-transcribe-1.0` |
| SAM parser | `meta-sam-parser` 0.0.6 or later (Python 3.10+) |
| Rate limits | Spark and SAM 3,000 RPM, Spark 4M TPM, Muse Image 150 RPM, Voice 256 concurrent streams, 60 min per session |

## Calls

| # | Use | Model | Endpoint | Parameters | When | Per night (expected) | Cost per call (est.) |
|---|---|---|---|---|---|---|---|
| 1 | Detect new object and write unit card | muse-spark-1.3 | POST /v1/responses | `reasoning.effort: medium`, one `input_image` (warped JPEG, base64) plus `input_text` (name, known boxes JSON), `text.format` json_schema `unit_card`, `strict: true`, `store: false` | Each summon | 8 | $0.010 |
| 2 | GM narration | muse-spark-1.3 | POST /v1/responses | `reasoning.effort: low`, `store: false` with no `previous_response_id` chain (privacy audit 2026-10-28, ADR-0012), json_schema `gm_turn`, strict, stable system prompt first for caching | Night start, each turn, sunrise | 10 | $0.008 |
| 3 | Free-form command fallback | muse-spark-1.3 | POST /v1/responses | `reasoning.effort: minimal`, json_schema `command_parse` with enums from live IDs, `store: false` | Grammar fails | 15 | $0.003 (cut, F12) |
| 4 | Recap | muse-spark-1.3 | POST /v1/responses | `reasoning.effort: low`, json_schema `recap` | Sunrise or defeat | 1 | $0.008 |
| 5 | Returning object match | muse-spark-1.3 | POST /v1/responses | Up to 6 crops plus new crop, json_schema `match`, effort low | Next night ties | 0 to 3 | $0.004 (Could) |
| 6 | Summon masks | sam-3.1 | POST /v1/responses | Box prompts for all known objects plus the new one, `stream: true`, `metadata: {include_confidence: "true", mask_encoding: "one_bit"}` | Each summon | 8 | $0.0025 |
| 7 | End Turn re-anchor | sam-3.1 | POST /v1/responses | Same as 6 with tracker boxes padded 20% | Each End Turn plus retries | 12 | $0.0025 |
| 8 | Recovery concept prompt | sam-3.1 | POST /v1/responses | `input_text` is the noun label, one concept per request | Not found by box or point | 0 to 2 | $0.0025 |
| 9 | Calibration auto-detect | sam-3.1 | POST /v1/responses | Concept "white paper" | Calibration | 0 to 1 | $0.0025 |
| 10 | Replay tracking | sam-3.1 | POST /v1/responses | `input_video` with `file_id`, box prompts at the first frame of each segment (multi-frame markers), `metadata: {propagation_direction: "forward", mask_encoding: "one_bit"}`, `stream: true` | Sunrise with consent | 1 | $0.08 (about 400 frames) |
| 11 | Replay upload and delete | Files API | POST /v1/files, DELETE /v1/files/{id} | `purpose: "user_data"`, `expires_after: {anchor: "created_at", seconds: 86400}` | Sunrise | 1 + 1 | $0 |
| 12 | Sprite restyle | muse-image-1.0 | POST /v1/responses | `input_text` prompt plus `input_image` crop (plus style anchor). Tool `image_generation` with `enable_web_search: false`, `enable_image_search: false`, `enable_shell: false`, `reasoning_strength: "low"`, `size: "1024x1024"`, `output_format: "png"`. `previous_response_id` chain within a night | Each new object | 8 | $0.01 |
| 13 | Summon voice | muse-voice-transcribe-1.0 | wss realtime | Handshake with `mode: "ENDPOINTING"` | Summon | 1 session | $0.18 per hour |
| 14 | Night voice | muse-voice-transcribe-1.0 | wss realtime | Handshake with `mode: "DIARIZATION"`, keywords with unit and player names | Voice claim to sunrise | 1 session | $0.18 per hour |
| 15 | Glimmer recap | Muse Glimmer 30B (Apache 2.0) | Local OpenAI-compatible server | Plain chat | Sunrise | 0 to 1 | $0 local (Could) |
| 16 | Dev scaffolding | Muse Code | CLI | Standard mode, Contributor off | Development | n/a | n/a |

Structured output shape: `text: {format: {type: "json_schema", name: "<schema>", schema: {...}, strict: true}}`. Strict mode needs `additionalProperties: false` on every object and every property listed in `required`.

## Model limits

| Model | Limits |
|---|---|
| Muse Spark 1.3 | Up to 50 images per request. Boxes on a normalized 0 to 1000 grid that can slightly exceed it, so clamp. Reasoning effort `none` returns HTTP 400 |
| SAM 3.1 | 16 prompted objects per frame (DeskTop uses 12). 15,000 frames per video request. Minimum 50 frames billed per video request. MP4 H.264 only. One concept per request. Empty `output_text` means zero matches, a normal result |
| Muse Image 1.0 | `background` is always opaque. `content_policy_violation` returns HTTP 400 |
| Voice | 25 languages including Tagalog with code-switching (Cebuano and Hiligaynon not included). Keywords fixed at session start. Labels session-scoped. 60 min max session |
| Files API | Upload up to 1 GiB. 100 GiB team storage. Files never expire unless `expires_after` is set (3,600 to 2,592,000 s) |

## SAM prompt format

Coordinates in warped-frame pixels, `w` and `h` are the warped frame size.

```text
<0f>1<|box;x1=402;y1=311;x2=488;y2=397;w=1280;h=853|>,2<|box;x1=640;y1=120;x2=702;y2=180;w=1280;h=853|>
```

Build prompts with `meta_sam_parser.build_object_prompt`. The builder uses exclusive right and bottom edges, the wire format inclusive. Let the builder handle it. Each output record looks like `<0f>1<|box;...;c=0.96|><|mask;...|>`.

```json
{
  "model": "sam-3.1",
  "input": [{ "type": "message", "role": "user", "content": [
    { "type": "input_text", "text": "<0f>1<|box;...|>,2<|box;...|>" },
    { "type": "input_image", "image_url": "data:image/jpeg;base64,..." }
  ]}],
  "stream": true,
  "metadata": { "include_confidence": "true", "mask_encoding": "one_bit" }
}
```

## Verify list (Phase 1 smoke tests, record answers in `docs/rules-notes.md`)

| Item | Check | Fallback |
|---|---|---|
| A6 structured output layout | One `responses.create` with `text.format` json_schema | Chat Completions `response_format` everywhere |
| `build_object_prompt` argument names | `help(meta_sam_parser.build_object_prompt)` | Read package source |
| Stream parser and `decode_mask_to_raster` names | `dir(meta_sam_parser)` | Read package source |
| Files `expires_after` | Direct arg, else `extra_body` | Upload without it, rely on DELETE |
| Muse Image latency | Time 20 calls (target 30 s) | Pre-generate demo sprites |
| Voice handshake | Quickstart with DIARIZATION, languageBias, keywords | ENDPOINTING |

Smoke scripts: `backend/smoke/spark.py`, `sam.py`, `image.py`, `voice.py`, `files.py`. Save each raw response under `fixtures/`.
