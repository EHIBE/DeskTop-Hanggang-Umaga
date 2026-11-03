---
title: Reliability and fallbacks
purpose: Timeouts, retries, circuit breaker, graceful degradation, Demo Safe Mode and all 31 edge cases
read_when: [writing any external call, error path, or Demo Safe Mode, handling a failure]
canonical_for: [timeouts, retry policy, breaker, degradation map, Demo Safe Mode contents, edge case table]
sources: [docs/DeskTop_PRD.md#10-non-functional-requirements, docs/DeskTop_PRD.md#14-edge-cases-and-failure-handling, docs/DeskTop_PRD.md#flow-f10-error-recovery]
status: active
last_verified: 2026-11-04
related: [docs/architecture/meta-api-integration.md, docs/delivery/demo-runbook.md, docs/design/copy-deck.md]
---

# Reliability and fallbacks

The night must finish even when the network or a model fails. Every external call has a timeout, limited retries and a local fallback, and Demo Safe Mode plays a whole night offline.

## Key facts

| Policy | Value |
|---|---|
| Timeouts | Spark 20 s, SAM image 10 s, SAM video 120 s, Muse Image 45 s, Files upload 60 s |
| Retries | Up to 2, backoff 0.5 s then 1 s, jitter up to 250 ms, honor Retry-After. No retry on HTTP 400 |
| Breaker | 3 consecutive failures on one model opens its fallback for 2 minutes |
| Crash recovery | Electron restarts backend, resume at turn start within 15 s |
| Rule | Fail closed. An error never skips consent, token check, cost meter or move validation |

## Graceful degradation (NFR-15)

| Down | Fallback | Player sees |
|---|---|---|
| SAM | Tracker positions with "?" badge and tap confirm | `track.uncertain` when needed |
| Muse Image | Placeholder sprites | Nothing |
| Spark | Line bank narration, local grammar, class default cards | Nothing or `net.down` |
| Voice | Tap controls and the `voice.down_banner` line. Voice problems retries | `net.down` |
| Credits at $120 | Block paid calls, Demo Safe Mode | `credits.low` |

## Demo Safe Mode (FR-50)

| Switch | Effect |
|---|---|
| Sprites and cards | From cache and assets |
| Narration | Line bank |
| Commands | Tap only. Voice is a paid call, so no session starts (`allows_voice` false) |
| SAM re-anchor | On by default, toggle to tracker-only (`demo_safe.sam`) |
| SAM summon and between-turn recovery | Off |
| Other paid calls | Off |
| Module | `backend/game/demo_safe.py` (`DemoSafeMode`), settings `demo_safe` and `demo_safe_sam` |

Done when: a night completes all 8 turns with Wi-Fi off.

## Edge cases

| # | Scenario | Detection | Response | Message key |
|---|---|---|---|---|
| 1 | Hand covers a piece | Tracker failure with motion | Freeze. Re-lock. After 5 s one SAM call | `endturn.hands` (after 5 s) |
| 2 | Hands on desk at End Turn | Frame difference | Wait up to 3 s for stillness | `endturn.hands` |
| 3 | Object falls off the desk | Centroid outside play area or no match | Lost (F22, `rules/lost.py`: `off_desk` flag at the End Turn snapshot, wiring in progress) | `unit.lost`, `lost.out` |
| 4 | Lost object placed back | Signature match near edge | Found when the centroid is back inside the play area at the next End Turn snapshot, start reset to the new spot | `unit.found`, `lost.back` |
| 5 | Voice misheard | "hindi" or X | Remove chip | `cmd.cancel` |
| 6 | Order not understood | Grammar fails | No chip | `cmd.unknown` |
| 7 | Two people talk at once | Two open turnIds | Drop both | `cmd.overlap` |
| 8 | New object mid-night | No matching ID | Ignore, exclude from prompts | "?" outline only |
| 9 | Lighting changes | Brightness over 30% change | Lower tracker trust, more recovery | `calib.dark` |
| 10 | Camera bumped | Baseline diff on the still frame at End Turn (built M10) | Pause, keep state. Resume checks again, Continue Anyway takes a new baseline | `cam.moved` |
| 11 | Two similar objects | Signatures within 0.05 or IoU swap | Tracker priors, then ask | `track.similar` |
| 12 | More than 16 objects | Spark count | Use 12, ignore extras | `summon.full` |
| 13 | Stacked objects | Overlap over 60% | Both Uncertain | `summon.stack` |
| 14 | Zero SAM matches | Empty output_text | Normal result, run recovery | `track.uncertain` if unresolved |
| 15 | Meta API outage | Breaker opens | Fallbacks, offer Demo Safe Mode | `net.down` |
| 16 | Slow network | p90 over 2x target for 3 calls | Placeholders, local narration first | `net.slow` |
| 17 | Credit exhaustion | api_usage at $120, or 402 or 429 with no retry window | Block paid calls, Demo Safe Mode | `credits.low` |
| 18 | Player leaves | Leave tap, or silent label for 3 turns (prompt only) | Units unowned | `player.left` |
| 19 | Kubo moved | Over 2 cm | Warn, no penalty | `kubo.moved` |
| 20 | Charm or wall moved too far | Illegal move | Block End Turn | `move.too_far` |
| 21 | Push target off desk | Rules computes outside | Unit out 1 turn | `tik.thrown` |
| 22 | Push or steal ignored | 20 s timeout | Accept current state | `effect.timeout` |
| 23 | Duwende killed, object off desk | Rules event | Show return mark | `duw.back` |
| 24 | Spark invalid JSON | Pydantic failure | Repair, then fallback | None |
| 25 | Muse Image content block | HTTP 400 content_policy_violation | Placeholder, no same-prompt retry | None |
| 26 | Sprite keying fails | Alpha coverage check | Other key, SAM cutout, placeholder | None |
| 27 | Voice session hits 60 min | Close 1011 | New session, re-claim | `voice.reclaim` |
| 28 | Mic picks up game audio | Only if TTS on | Send silence while TTS plays | None |
| 29 | Backend crash | Child process exit | Restart, restore autosave | `restore` |
| 30 | Webcam busy | OpenCV open failure | Device list | `cam.busy` |
| 31 | No recording consent | Consent screen | Night without recording, Replay hidden | None |

Proposed keys (`kubo.moved`, `tik.thrown`, `effect.timeout`, `voice.reclaim`, `cam.busy`) are listed in `design/copy-deck.md`.

## Implementation rules

- One retry and breaker implementation inside `meta_client.py`. No ad hoc retries elsewhere.
- Retry only idempotent calls. A Muse Image or Spark call is safe to retry, a Files upload is checked by listing first.
- Catch specific exceptions (timeout, API status). Never a bare except.
- Narration never blocks the next turn.
