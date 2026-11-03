---
title: Security and privacy
purpose: Threat model, data inventory, Electron and local server hardening, and the OWASP checklist for this stack
read_when: [touching main, preload, server.py, meta_client, recording, uploads, any input path]
canonical_for: [threat model, data inventory, hardening checklist, privacy rules]
sources: [docs/prompts/FEATURE_PROMPT.md#5-security-guardrails-mapped-to-owasp-top-102025, docs/DeskTop_PRD.md#10-non-functional-requirements, app/src/main/index.ts, app/src/preload/index.ts, app/src/renderer/index.html]
status: active
last_verified: 2026-10-29
related: [docs/decisions/ADR-0103-electron-hardening.md, docs/architecture/websocket-protocol.md, docs/architecture/data-model.md]
---

# Security and privacy

DeskTop has no accounts, so the main assets are the Meta API key, the players' camera and mic data, and the credit balance. The design keeps all three on the laptop and treats the renderer and every model output as untrusted.

## Key facts

| Asset | Protection |
|---|---|
| MODEL_API_KEY | Electron safeStorage, passed to the backend by env, never in renderer, logs, repo or docs |
| Local server | 127.0.0.1 only, per-launch DESKTOP_TOKEN on every request, constant-time compare |
| Video and audio | Local. Only frames, crops, live audio and a consented proxy leave |
| Credits | Cost meter, $120 hard stop, breaker |
| Players | Consent before recording, profanity filter, no faces in frame |
| Reviewer | `desktop-electron-security-reviewer`, `desktop-privacy-cost-auditor`, `security-review` skill |

## Threat model

| Threat | Vector | Control |
|---|---|---|
| Another local process drives the game or reads frames | HTTP or WS on localhost | Bind 127.0.0.1, token, Origin check |
| Key theft | Renderer compromise, logs, git | safeStorage, env only, scrubbed logs, secret scan |
| Renderer code execution | Malicious content, open links | sandbox, contextIsolation, CSP, openExternal allowlist |
| Prompt injection | Spoken text, typed names, object labels | Data inside JSON fields, strict schemas, enum IDs, clamps |
| Path traversal | IDs used in file paths | UUID names, resolve and check prefix under user data root |
| Command injection | ffmpeg arguments | List args, no shell, no player text |
| Cost runaway | Retry loops, spam | Retry cap, breaker, hard stop, per-turn SAM cap, 1 re-roll |
| Privacy leak | Raw video upload, long retention | No raw upload, consent, expires_after, explicit DELETE |
| Offensive content | Names, generated text, sprites | Profanity and banned-word filters, content policy fallback |

## Data inventory

| Data | Stays local | Sent to Meta | Retention |
|---|---|---|---|
| Full camera video | Yes | Never | Until deleted |
| Warped single frames | Yes | Yes (Spark, SAM) | Per call |
| Mask crops | Yes | Yes (Muse Image) | Per call |
| GM narration input | Yes | Yes (Spark): unit names, classes, HP, game ids, events. Players appear as P1 to P4 and the names are swapped back locally | Per call, `store: false` |
| Summon name | Yes | Yes (Spark), after the profanity filter | Per call, `store: false` |
| Mic audio | Live only | Streamed (Voice), plus recognizer keywords with creature words and unit names, never player names | Not stored locally. Transcripts are not stored |
| Highlight proxy clip | Yes | With consent (Files, SAM video), a 960 px 10 FPS cut of 4 to 6 highlights only | 24 h `expires_after`, deleted in a `finally` after tracking (built Phase 14) |
| Database, sprites, recordings | Yes | Never | Until delete campaign |

All calls in Standard mode, never Contributor mode. Every `responses.create` call sets `store: false` (Spark summon and narration, SAM, Muse Image), so no response is kept for chaining.

## Electron hardening checklist (ADR-0103)

- [x] `sandbox: true`, `contextIsolation: true`, `nodeIntegration: false`, `webSecurity: true`
- [x] Preload exposes only `getConfig()`, `getKeyStatus()`, `saveKey()` and `showReel()`. No `electronAPI`, no raw `ipcRenderer`. `desktop:show-reel` accepts only `reel_<name>.mp4`, checks the sender and refuses links and paths outside the recordings folders
- [x] `ipcMain` handlers validate the sender (main frame and exact renderer URL)
- [x] `setWindowOpenHandler` denies, `shell.openExternal` only for allowlisted https origin and path
- [x] CSP keeps `default-src 'self'`, adds `connect-src` for the backend only, plus `object-src`, `base-uri`, `form-action` and `frame-src` set to none
- [x] Remove the scaffold `ping` handler
- [x] Permission requests and checks denied by default. Navigation, redirects and webviews blocked
- [x] Free port and fresh token at every backend start (B11 closed in M3)
- [ ] Electron fuses (B12, needs approval)
- [x] Disable auto-update publish (example.com placeholder)

## Local server checklist

- [x] uvicorn `--host 127.0.0.1` and `--no-access-log`
- [x] Token on every HTTP route (`X-Desktop-Token`) and WS connect (subprotocol), `hmac.compare_digest`, close 1008 on mismatch
- [x] WS Origin check against `DESKTOP_ALLOWED_ORIGINS`
- [x] No CORS middleware
- [x] FastAPI docs, redoc and openapi URLs off
- [x] Pydantic `extra="forbid"` and strict types on every message, 16 KiB cap
- [ ] State-machine check on every action
- [ ] Minimal error detail to the renderer

## OWASP Top 10:2025 summary

Summary. Canonical: `docs/prompts/FEATURE_PROMPT.md` section 5.

| Category | Key control here |
|---|---|
| A01 Access control | Token, 127.0.0.1, ID and state checks, consent gate, fixed outbound hosts, path prefix checks |
| A02 Misconfiguration | Electron flags, CSP, no CORS, docs off, no debug output |
| A03 Supply chain | No new deps without approval, lockfile, pinned requirements, npm audit |
| A04 Crypto | safeStorage, crypto.randomBytes token, compare_digest |
| A05 Injection | Parameterized SQL, list-arg subprocess, untrusted text as data, React escaping, profanity filter |
| A06 Insecure design | Abuse cases, server-side limits, cost meter, models never write numbers |
| A07 Authentication | Per-launch token, regenerated on restart, no cookies so no CSRF |
| A08 Integrity | H.264 only, size check, no pickle, validated JSON |
| A09 Logging | Log token mismatch, rejects, gm_invalid, breaker, hard stop. Never log secrets |
| A10 Exceptional conditions | Fail closed, rollback autosave, specific exceptions |

## Release checks

- Secret scan before any push: `git log -p | Select-String -Pattern "MODEL_API_KEY|sk-|Bearer "` (PowerShell).
- Check staged files before every commit. Never stage `.env`, keys, recordings, user data or `*.sqlite`.
- Repo is public and organizers get a perpetual license (R17). Nothing confidential goes in.
