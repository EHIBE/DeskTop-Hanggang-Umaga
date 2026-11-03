---
title: Live API runbook
purpose: Step-by-step plan for the first live run against the Meta Model API with a $15 budget, including stop rules and failure triage
read_when: [going live with the Muse key, running smoke scripts, generating assets, a live call fails]
canonical_for: [live run order, live budget, stop rules, failure triage]
sources: [backend/smoke, backend/meta_client.py, backend/config.py, docs/rules-notes.md, docs/architecture/meta-api-integration.md, docs/architecture/cost-and-budget.md, eval/run_eval.py, docs/architecture/reliability-and-fallbacks.md]
status: planned
last_verified: 2026-11-03
related: [docs/rules-notes.md, docs/architecture/meta-api-integration.md, docs/architecture/cost-and-budget.md, docs/architecture/reliability-and-fallbacks.md, docs/engineering/troubleshooting.md]
---

# Live API runbook

This is the order of operations for the first live calls with the Muse key, with EHIBE watching the screen. No live call has been recorded yet, so every "Works" cell in `docs/rules-notes.md` is still empty.

## Key facts

| Fact | Value |
|---|---|
| Live spend budget today | $15 (decision of 2026-11-03). The in-app meter still warns at $90 and stops at $120 |
| Expected smoke spend | Under $0.10 for the six smoke scripts (`docs/rules-notes.md`). Asset script cost is Unverified, see below |
| Base URL | `https://api.meta.ai/v1`. Realtime: `wss://api.meta.ai/v1/asr/realtime` |
| Models | `muse-spark-1.3`, `sam-3.1`, `muse-image-1.0`, `muse-voice-transcribe-1.0` |
| Timeouts | Spark 20 s, SAM image 10 s, SAM video 120 s, Muse Image 45 s, Files 60 s |
| Retries and breaker | 2 retries. Breaker opens after 3 consecutive failures for 120 s |
| Where results go | `docs/rules-notes.md`, tables "Phase 1 smoke test findings" |
| Usage database | `%APPDATA%\DeskTop\desktop.sqlite`, table `api_usage` (or `DESKTOP_DATA_DIR`) |
| Fixtures | `fixtures/` at the repo root, keys scrubbed by the smoke helpers |
| Who types the key | EHIBE only. Agents never read `backend/.env` |

## Preconditions

Do all of these before the first command. Stop if any is missing.

- Credits claimed. Status: Unverified until EHIBE records it in `docs/rules-notes.md` (row "Credits claimed").
- Contributor mode off. EHIBE confirmed this on 2026-11-03. Record it in `docs/rules-notes.md` (row "Contributor mode off").
- The key is in the app: run `npm --prefix app run dev`, paste the key on KeySetup, press Save. It is stored with Electron safeStorage in `<userData>\model-key.bin`.
- The key is in `backend\.env` as `MODEL_API_KEY=...`, typed by EHIBE. The smoke scripts load it with `load_dotenv(backend/.env)` and stop with "MODEL_API_KEY is empty" if it is missing. `.env` is git-ignored.
- Inputs exist: `eval\desk1.jpg`, `eval\mug_crop.png`, `eval\clip.mp4` (H.264). They are Manual: EHIBE.
- A microphone is plugged in for the voice step.
- Open a PowerShell window and `cd backend` once. All commands below run from `backend`.

## Order of runs

Run top to bottom. Record each result in `docs/rules-notes.md` before moving on.

| # | Command (from `backend`) | Proves | Record |
|---|---|---|---|
| 1 | `.venv\Scripts\python -m smoke.spark` | Which of three request shapes returns structured output from Spark (A6). Writes `spark_line.json` | "Spark structured output" row: shape, seconds |
| 2 | `.venv\Scripts\python -m smoke.sam --image ..\eval\desk1.jpg --box 1,x1,y1,x2,y2 --box 2,x1,y1,x2,y2` | SAM accepts box prompts and the parser returns masks. Writes `sam_boxes.jsonl` and `.txt` | "SAM box prompts" row: argument names, latency |
| 3 | `.venv\Scripts\python -m smoke.sam --image ..\eval\desk1.jpg --concept "white paper" --name sam_concept` | SAM concept prompt for calibration. Writes `sam_concept.jsonl` | Same row, note concept result |
| 4 | `.venv\Scripts\python -m smoke.image --crop ..\eval\mug_crop.png --runs 20` | Muse Image latency (A9): min, median, max. Writes `sprite_kubo.png` | "Muse Image latency" row |
| 5 | `.venv\Scripts\python -m smoke.voice --mode DIARIZATION --seconds 10` | Realtime handshake and event field names, with two speakers. Writes `voice_diarization.jsonl` | "Voice DIARIZATION handshake" row |
| 6 | `.venv\Scripts\python -m smoke.files --clip ..\eval\clip.mp4` | Files upload with `expires_after` and delete | "Files expires_after" row |
| 7 | `.venv\Scripts\python -m smoke.assets --date 2026-11-03` | Generates placeholder and enemy sprites. `--only placeholders`, `enemies` or `all` (default) | Note counts and any content policy block |

Replace `x1,y1,x2,y2` with real pixel boxes from `desk1.jpg`. Step 7 needs `--date` (required). Use today's date.

Run step 4 with `--runs 3` first if the budget feels tight. Muse Image costs $0.01 per image, so 20 runs is about $0.20.

Asset script cost: Unverified. The script makes one Muse Image call per sprite plus retries on validation failure. Count the specs in `backend/smoke/assets.py` and multiply by $0.01 before running, then confirm with the usage query below.

After step 7, rate the sprites (eval E5) and keep or delete them by hand. Sprites in `assets/sprites/` ship with the game, so check each file for an unwanted logo or text.

## After the smoke scripts

- Play one short night in the app with the key saved, then end it.
- From the repo root, run `backend\.venv\Scripts\python eval\run_eval.py cost --db "$env:APPDATA\DeskTop\desktop.sqlite"`. It reports only finished nights, so the smoke spend does not show there.
- To see all spend including smoke runs, query `api_usage` read only. From the repo root:

```powershell
backend\.venv\Scripts\python -c "print(__import__('sqlite3').connect('file:' + __import__('os').environ['APPDATA'] + '/DeskTop/desktop.sqlite?mode=ro', uri=True).execute('select model, count(*), round(sum(cost_usd), 4) from api_usage group by model').fetchall())"
```

- Unverified: the table has the columns `model`, `kind`, `cost_usd`, `ok`, `latency_ms` and `ts` (they are used by `eval/run_eval.py`). If the query errors, read `backend/db/schema.sql`.

## Budget

- Hard budget today is $15. The app's own stop is $120, so the $15 line is manual.
- Check the total after every two steps with the query above. Stop and report if the sum passes $10.
- Hitting $120 in the app turns Demo Safe Mode on. Smoke scripts also respect the $120 stop.

## Stop rules

Stop all live runs and tell EHIBE if any of these happen.

| Trigger | Action |
|---|---|
| Any HTTP 401 or 403 | Stop. The key is wrong, revoked, or the account lacks access. Do not retry in a loop |
| Spend over the $15 budget | Stop. Record the total |
| Any doubt that Contributor mode is off | Stop until EHIBE confirms in the account settings |
| HTTP 402, or 429 with no retry window | The meter forces Demo Safe Mode. Stop and check credits |
| Content policy block (HTTP 400) on Muse Image | Do not retry the same prompt. Record it and change the prompt |
| The key appears in any output or file | Stop. Rotate the key. Do not commit |

## Recording fixtures with keys stripped

- The smoke helpers (`backend/smoke/__init__.py`) call `scrub()` before writing fixtures. Secret keys are replaced with `[redacted]`.
- After each run, open the new files under `fixtures/` and search for the first 6 characters of the key, `Authorization` and `Bearer`. None should appear.
- Do not commit until that search is clean. EHIBE runs the commit.
- Tests use recorded fixtures only and make no paid calls.

## Failure triage

Canonical for fallbacks: `docs/architecture/reliability-and-fallbacks.md`.

| Model | Symptom | Likely cause | Fallback that kicks in |
|---|---|---|---|
| Spark | Timeout at 20 s, or invalid JSON | Slow network, wrong structured output shape (A6) | Repair attempt, then class-default card and line-bank narration |
| Spark | All three shapes fail in `smoke.spark` | Wrong endpoint or schema layout | Game stays playable on defaults. Record which error each shape gave |
| SAM 3.1 | Empty masks | Boxes outside the image, wrong coordinates | Tracker positions with a "?" badge and tap confirm |
| SAM 3.1 | Timeout at 10 s | Large image or network | Same as above |
| Muse Image | Content policy block | Prompt or crop flagged | Placeholder sprite |
| Muse Image | Timeout at 45 s | Slow generation | Placeholder sprite, sprite retried in the background |
| Voice | No events, or handshake rejected | Wrong field names, no mic, key lacks the model | Tap controls and the voice-down banner. Voice problems retries |
| Files | Upload rejected | `expires_after` shape wrong, clip not H.264 | Replay falls back to the anchor box path |
| Any | 3 failures in a row | Network or outage | Breaker opens for 120 s, then local fallback |
| Any | 402 or 429 with no retry window | Credits exhausted | Demo Safe Mode and `credits.low` |

On 401 and 403 the client raises `MetaRequestError` with no retry (`_is_rejected_request` covers HTTP 400 up to 499 except 408, 409 and 429). It does not force Demo Safe Mode, so the game falls back per call and keeps asking. That is why a 401 or 403 is a manual stop rule. Unverified: the exact error text the API returns, which the first live run will show.
