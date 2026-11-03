---
title: Troubleshooting
purpose: Symptom, cause and fix table for players and developers, including how to run the backend by hand
read_when: [the game will not start, the camera or mic fails, the UI sticks on Connecting, a warning appears on first run]
canonical_for: [symptom to fix table, manual backend run command, log locations]
sources: [docs/how-to-run.md, docs/architecture/reliability-and-fallbacks.md, app/src/main/backend.ts, backend/server.py, backend/capture/camera.py, docs/design/copy-deck.md]
status: active
last_verified: 2026-11-03
related: [docs/how-to-run.md, docs/architecture/reliability-and-fallbacks.md, docs/engineering/setup-windows.md, docs/delivery/release-and-packaging.md]
---

# Troubleshooting

Find the symptom in the table, read the cause, then apply the fix. Players start with the first table and developers continue to the second.

## Key facts

| Fact | Value |
|---|---|
| Backend log | `%APPDATA%\DeskTop\logs\backend.log`. Rewritten on each app launch. Token and key are redacted |
| Data folder | `%APPDATA%\DeskTop`, or the folder in `DESKTOP_DATA_DIR` |
| Health check | `GET http://127.0.0.1:<port>/health` with header `X-Desktop-Token`. Returns `{"ok": true}` |
| Backend start wait | 20 s for the first healthy answer |
| Restarts after a crash | Up to 5, waiting 1, 2, 4, 8 and 8 s |
| Token rule | `DESKTOP_TOKEN` must be at least 32 characters. The app makes 64 hex characters |
| Offline play | Demo Safe Mode plays a full night without the network |

## Player problems

| Symptom | Cause | Fix |
|---|---|---|
| Window stays on Connecting or Reconnecting | The backend did not start or became unhealthy. Common causes are a missing Python venv or a crash on import | Close the game and start it again. Open `backend.log` and read the last lines. If the venv is missing, run the install steps in `docs/how-to-run.md` |
| Stuck on Connecting after the backend log says it is running | The websocket was rejected for a wrong Origin or token. The log says "rejected websocket from an unexpected origin" or "with a missing or wrong token" | Restart the app so it makes a fresh token. The packaged `null` origin is accepted since ADR-0111 (`DESKTOP_PACKAGED`), unverified in a packaged run. See `docs/delivery/release-and-packaging.md` |
| Camera light on, picture is black, or a camera is marked "no picture" | Another program holds the real webcam and offers a virtual one, often NVIDIA Broadcast. The camera list marks cameras that only give black frames | Pick the camera that is not marked "no picture", or quit NVIDIA Broadcast and use the real webcam |
| "No camera found", or "Another app is using the camera" (`cam.busy`) | Zoom, Teams, the Windows Camera app or a browser tab holds the camera. Or no camera is plugged in | Close those apps, replug the camera, then pick it again in Calibration |
| Camera refused with a resolution message | The backend needs 1280x720 or more | Pick another camera mode or another camera |
| "Gumalaw ang camera! I-calibrate ulit." (`cam.moved`) | The camera was bumped. The game paused | Put the camera back and press Resume, or recalibrate |
| Voice shows "Voice down", or mic is missing | No microphone, mic blocked in Windows privacy settings, no key, or the network is down | Plug in a mic and allow desktop apps to use it in Windows Settings. Check the internet. Press Voice problems. Tap controls always work. Voice is off in Demo Safe Mode |
| "Walang recording ngayon" or "The replay needs ffmpeg" (`replay.no_ffmpeg`) | ffmpeg is not found | Run `winget install Gyan.FFmpeg`, reopen PowerShell, check `ffmpeg -version`, restart the game. The night plays fine without it |
| "Paubos na ang credits. Naka-Demo Safe Mode na." (`credits.low`) | Paid spend reached the $120 hard stop, or the API answered 402, or 429 with no retry window | Play on in Demo Safe Mode. Tapping, placeholder sprites and the line bank all work. Check your credits before the next live night |
| "Offline muna ang [feature]" (`net.down`) | A model call failed three times and its breaker opened for 2 minutes | Wait, or keep playing with the fallback. Tap controls and line bank cover it |
| "Medyo mabagal ang koneksyon" (`net.slow`) | Slow network | Keep playing. Local narration goes first |
| Windows shows "Windows protected your PC" (SmartScreen) when opening the zip build | The build is unsigned | Click More info, then Run anyway. The code is public on GitHub |
| A crash during a night | Any unexpected error | Start the game again and continue the campaign. Begin Night resumes at the start of the turn |
| Demo Safe Mode is on and I did not choose it | Credit stop, or the toggle on the Start screen | Turn it off on the Start screen if credits allow |

## Developer problems

### Run the backend by hand

The backend refuses to start without a token of at least 32 characters. Use the factory form, not `server:app`. From the repo root in PowerShell:

```powershell
cd backend
$env:DESKTOP_TOKEN = -join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
$env:DESKTOP_DEV = "1"
.venv\Scripts\python -m uvicorn server:create_app_from_env --factory --host 127.0.0.1 --port 8765
```

- `DESKTOP_DEV=1` loads `backend\.env` so `MODEL_API_KEY` is picked up. Without it the backend runs keyless.
- Test health in a second window: `Invoke-RestMethod -Uri http://127.0.0.1:8765/health -Headers @{ 'X-Desktop-Token' = $env:DESKTOP_TOKEN }`. Expect `ok : True`.
- Without the header every route returns 401. `/ws` also needs an `Origin` listed in `DESKTOP_ALLOWED_ORIGINS` and the subprotocols `desktop` and the token. A browser tab cannot connect by hand.
- `server.py` defines `create_app` and `create_app_from_env` only. There is no `server:app`.

### Table

| Symptom | Cause | Fix |
|---|---|---|
| `DESKTOP_TOKEN is missing or too short` on start | Token unset or under 32 characters | Set it as shown above |
| `DESKTOP_PORT must be between 1024 and 65535` | Bad port env | Use a port in range. The app picks a free one itself |
| `DESKTOP_DATA_DIR and APPDATA are both unset` | Running in a stripped shell | Set `DESKTOP_DATA_DIR` to a writable folder |
| `ModuleNotFoundError` for `fastapi`, `cv2` or `meta_sam_parser` | Wrong interpreter, or deps not installed | Use `backend\.venv\Scripts\python`. Run `backend\.venv\Scripts\python -m pip install -r backend\requirements.txt` |
| Venv creation fails | Python 3.13 not installed (the venv uses 3.13, ADR-0101) | `py -3.13 --version`. Install 3.13 |
| Backend exits right after start in the app | Import error or bad env | Read `backend.log`. Run the manual command above to see the traceback |
| `backend start failed: backend health check timed out` in the log | The backend took over 20 s, or the token header was wrong | Run manually and watch startup time. First import of OpenCV can be slow on a cold disk |
| Smoke script says `MODEL_API_KEY is empty` | `backend\.env` missing or key blank | EHIBE edits `backend\.env`. Agents never read it |
| `ffmpeg` not found though set in `DESKTOP_FFMPEG` | The variable was set after the app started, or the path is wrong. Main passes `DESKTOP_FFMPEG` to the backend since 2026-11-03 | Set the variable before launching, check the path, or put ffmpeg on PATH |
| Port already in use on 8765 | An earlier manual backend still runs | Stop it, or pass another `--port` |
| Backend exits when the app closes | The app sets `DESKTOP_PARENT_WATCH=1`, so the backend quits when its stdin closes | Expected. A manual run does not set it |
| Black frames in the camera test | `is_black` found a mean brightness at or under the limit | Pick another camera index or free the camera. See the player table |
| `npm --prefix app run dev` opens a window but nothing loads | Port conflict or an old `electron-vite` temp file | Close other dev servers. Delete stray `app\electron.vite.config.ts.*.mjs` files |
| Tests touch the network | They should not | Report it. Tests run offline on recorded fixtures |

## Where to look first

1. `%APPDATA%\DeskTop\logs\backend.log`
2. The manual run above, to see a traceback in the console
3. `docs/architecture/reliability-and-fallbacks.md` for what each fallback does
4. `docs/design/copy-deck.md` for the exact wording of each player message
