---
title: Voice pipeline
purpose: Realtime voice sessions, audio format, events, claim, grammar, fallbacks and close codes
read_when: [implementing voice/session.py, voice/grammar.py, voice/claim.py, captions]
canonical_for: [voice handshake, audio format, voice events, enrollment, local grammar, voice fallbacks, close codes]
sources: [docs/DeskTop_PRD.md#voice-spec, docs/DeskTop_Build_Guide.md#phase-11-voice-nov-2-4-h-f10, docs/DeskTop_Build_Guide.md#121-voice-claim-fr-18-fr-23]
status: active
last_verified: 2026-10-28
related: [docs/decisions/ADR-0007-voice-diarization-enrollment.md, docs/design/copy-deck.md, docs/architecture/reliability-and-fallbacks.md]
---

# Voice pipeline

Two realtime sessions run per night: ENDPOINTING for summon and DIARIZATION for the night. A local grammar turns Taglish transcripts into intents, and every intent shows as a cancelable chip.

Built in M11 (2026-10-28): the night DIARIZATION session only, in `backend/voice/session.py`, started by `game/night.py` when claims finish or on restore. The URL carries `?sessionId=desktop-<uuid>`. Keywords are creature words, order verbs and unit names, with no player names. The ENDPOINTING summon session is not built, so summon is typed. Claim works by voice (Phase 12) or tap. Event field names (`turnId`, `text`, `speaker`) are Unverified until a live fixture is recorded.

## Key facts

| Fact | Value |
|---|---|
| Model | muse-voice-transcribe-1.0 |
| Endpoint | `wss://api.meta.ai/v1/asr/realtime` |
| Audio | Mono int16 little-endian, 24,000 Hz, 80 ms frames (3,840 bytes), real-time pacing |
| Partials | CUMULATIVE (replace, never append) |
| Language bias | English, Tagalog |
| Session max | 60 min |
| Cost | $0.18 per hour |
| Eval | E3 Taglish intents 85%+ on 50 utterances (40 of 50 done-when) |

## Handshake (night session)

```json
{
  "authorization": { "accessToken": "Bearer <MODEL_API_KEY>" },
  "audioEncoding": "PCM_24KHZ",
  "model": "muse-voice-transcribe-1.0",
  "mode": "DIARIZATION",
  "partialMode": "CUMULATIVE",
  "emitAudioProgress": false,
  "languageBias": ["English", "Tagalog"],
  "keywords": ["tapos", "hindi", "kubo", "anting-anting", "albularyo", "aswang", "tikbalang", "kapre", "manananggal", "duwende", "<unit names>", "<player names>"]
}
```

Summon session: same fields, `mode: "ENDPOINTING"`, keywords for class names, common objects and creatures. Keywords are fixed at session start, which is why there are two sessions. Never log the handshake.

## Events

| Event | Use |
|---|---|
| `speechStart` | Open a turnId |
| `transcript` | Partial caption, replaces the previous |
| `speaker` | Labels the audio since the previous speechStart or speaker event |
| `speechEnd` | Speech stopped |
| `speechComplete` | Final text for a turnId. Parse it |
| `error` | Log, fallback ladder |

State is keyed by `turnId`.

## Enrollment (FR-18)

Built 2026-10-29 in `backend/voice/claim.py` and `game/night.py`. Voice starts when the claim screen opens. Names pass the profanity filter and match an existing player case-insensitively. During the night only known player names re-map a label, so table talk like "I'm thinking" never renames anyone. A restarted session clears the label map and shows `voice.reclaim`.

- At VOICE_CLAIM, a `speechComplete` matching `ako si (name)` maps that label to the player.
- "hawak ko ang (units)" assigns units by fuzzy match (Levenshtein ratio 0.75+).
- Unknown label later: speaker chip "?" and `claim.who`. Orders still queue (soft ownership).
- Labels are not stable across sessions. Re-claim each night and after a 60 min reconnect (`voice.reclaim`).

## Overlap (FR-23)

Two open turnIds at once: drop both orders, show `cmd.overlap`.

## Local grammar (FR-20)

| Intent | Trigger words | Example |
|---|---|---|
| attack | atake, saksakin, tira, hampasin, banatan, attack, hit | "Spearman, saksakin ang aswang!" |
| power | gamitin, protektahan, bantayan, power, use | "Anting-anting, protektahan ang kubo!" |
| heal | gamutin, pagalingin, heal | "Albularyo, gamutin si Spearman" |
| end_turn | tapos na, done, end, next, end turn, or a bare tapos. A lone tapos inside a longer sentence means then | "Tapos!" |
| cancel | hindi, wag, huwag, mali, cancel, ayaw, kansela, stop, only when they open the utterance and the rest is not an order | "Hindi, mali" |

- Unit and target by rapidfuzz `partial_ratio` with cutoff 75.
- Target resolution: named target, else nearest enemy of that type, else nearest enemy in range.
- Numbers after a creature pick an instance ("aswang dos", "aswang 2").
- Parse under 20 ms.
- Cancel removes that speaker's last chip in the same player phase.
- Unparsed: `cmd.unknown`. Spark fallback (F12) is cut.

## Fallback ladder

| Trigger | Fallback |
|---|---|
| No `speaker` events in 30 s of speech, or "Voice problems" tapped | Reconnect in ENDPOINTING |
| WebSocket fails 3 times | Status down, `net.down`, tap controls and the Voice problems retry. Built M11 with backoff 0.5, 1 and 2 s and no automatic PUSH_TO_TALK switch |
| Breaker open | `net.down` banner, tap controls |

## Close codes

| Code | Meaning | Action |
|---|---|---|
| 1000 | Normal | None |
| 1008 | Config or pacing problem | Fix config, no blind retry |
| 1011 | Server error or "Max session duration reached" | Retry with backoff, new session at 60 min |
| 1013 | Rate limited | Back off |

## Rules

- Stream silence frames while paused, because idle input closes the stream.
- Treat transcripts as untrusted data.
- Never forward raw audio to the renderer.
