---
title: Release and packaging
purpose: How the unsigned Windows zip with a portable Python backend is built, what was verified, and how to check it before release
read_when: [building the release zip, changing electron-builder.yml, fixing a packaged-build bug, preparing the submission download]
canonical_for: [release artifact, packaging steps, Electron fuses, release checklist]
sources: [app/package.json, app/electron-builder.yml, app/scripts/stage-backend.mjs, app/src/main/backend.ts, app/src/main/index.ts, backend/requirements.txt, docs/engineering/setup-windows.md, docs/how-to-run.md]
status: active
last_verified: 2026-11-04
related: [docs/how-to-run.md, docs/engineering/setup-windows.md, docs/engineering/troubleshooting.md, docs/delivery/submission-checklist.md, docs/delivery/live-api-runbook.md, docs/decisions/ADR-0111-packaged-build-and-origin.md]
---

# Release and packaging

The release is an unsigned zip of the unpacked Windows app. It carries its own portable Python 3.13 with every backend package, so a player needs neither Node nor Python. Built and smoke tested on 2026-11-04.

## Key facts

| Fact | Value |
|---|---|
| Artifact | `release/DeskTop-1.0.0-win.zip`, unsigned, from `app/dist/win-unpacked` |
| Size | 327.1 MB zipped, 875 MB unpacked |
| SHA-256 | `A6BE68E4E84B55849B592FBB66E7D5CBB273E665C58E747911DDB8F3ACFBD8CF` (final build at commit 5e0cff7, 2026-11-04, 323.8 MB. Tests folders in site-packages excluded. Camera list and live preview checked in the packaged app. A rebuild changes it) |
| Build command | `npm --prefix app run dist:win` |
| Staging only | `npm --prefix app run bundle:backend` |
| Platform | Windows only |
| App id | `com.ehibe.desktop`, product name `DeskTop`, executable `DeskTop.exe` |
| Backend when packaged | `resources/backend`, Python at `resources/backend/python/python.exe` |
| Assets when packaged | `resources/assets` (the backend finds `assets/` two levels above `gm/` and `replay/`) |
| Data and logs | `%APPDATA%\DeskTop`, passed by main as `DESKTOP_DATA_DIR`. Log at `logs\backend.log` |
| Signing | None. SmartScreen will warn |
| ffmpeg | Not bundled. Replay and recording need it on PATH or `DESKTOP_FFMPEG` |

## How the build works

1. `app/scripts/stage-backend.mjs` builds `app/staging` (git ignored). It asks the venv Python for `sys.base_prefix`, then copies `python*.exe`, `python*.dll`, `vcruntime*.dll`, `DLLs/` and `Lib/` from that base install. It skips tkinter, idlelib, ensurepip, test folders and `__pycache__`.
2. It copies the venv `Lib/site-packages` into the staged `Lib/site-packages`, leaving out dev tools (mypy, pytest, coverage, ruff, pygments, pip and their helpers).
3. It copies `backend/*.py` and the packages `capture`, `db`, `game`, `gm`, `replay`, `rules`, `vision`, `voice`, including `db/schema.sql` and `gm/data`. It leaves out tests, smoke, `.env`, databases, logs and recordings. It copies `assets/` beside the backend folder.
4. It runs the staged Python with a minimal environment (no `PYTHONHOME`, venv off `PATH`) and imports cv2, numpy, fastapi, uvicorn, openai and `server`. The build stops if that fails.
5. `electron-builder.yml` maps `staging/backend` to `resources/backend` and `staging/assets` to `resources/assets` through `extraResources`.
6. `dist:win` then runs `npm run build` (typecheck and `electron-vite build`) and `electron-builder --win --dir`, which writes `app/dist/win-unpacked`.

Staging takes about a minute. Main uses `process.resourcesPath/backend` and `python/python.exe` when `app.isPackaged`. Dev still uses `backend/` and `.venv`.

## Electron fuses

Set in `app/electron-builder.yml` under `electronFuses`. The build log line `executing @electron/fuses` confirmed they were applied to `DeskTop.exe`.

| Fuse | Setting |
|---|---|
| runAsNode | Off |
| enableCookieEncryption | On |
| enableNodeOptionsEnvironmentVariable | Off |
| enableNodeCliInspectArguments | Off |
| enableEmbeddedAsarIntegrityValidation | On |
| onlyLoadAppFromAsar | On |

The app still loaded from the asar and spawned the backend with these settings. `--remote-debugging-port` is a Chromium switch and still worked.

## Packaged origin

The packaged renderer loads from `file://` and Chromium sends Origin `null`. Main sets `DESKTOP_PACKAGED=1` and the backend then accepts `null` (ADR-0111). Verified on 2026-11-04: the unpacked app's `/ws` was accepted and the renderer showed the language pick.

## Smoke result, 2026-11-04

Run from `app/dist/win-unpacked` with `DeskTop.exe --remote-debugging-port=9444` and no key. No campaign was created.

- Backend log: `Uvicorn running on http://127.0.0.1:57193`, then `"WebSocket /ws" [accepted]` and `desktop.server websocket accepted`.
- Renderer page text read over the debug port: the language pick (Filipino, English), so it got past Connecting.
- The app was stopped by killing its processes, so the clean window close path and the child exit were not checked.

## Secret scan of the unpacked tree

- No `.env`, `model-key.bin`, `*.sqlite`, `backend.log`, `*.key`, recordings or wav files.
- No `sk-` style string in `resources/backend` sources, `gm/data` or `resources/assets`.
- One long-token hit: a URL slug in `gm/data/ATTRIBUTION.md` (a public word list name). Not a secret.
- The scan covered backend sources, data files and assets. It did not scan binaries inside site-packages.

## Zip step

```powershell
npm --prefix app run dist:win
Compress-Archive -Path app\dist\win-unpacked\* -DestinationPath release\DeskTop-1.0.0-win.zip -Force
Get-FileHash release\DeskTop-1.0.0-win.zip -Algorithm SHA256
```

## Checklist

| # | Check | Status |
|---|---|---|
| 1 | Build runs without errors | Done 2026-11-04. The renderer was built with `electron-vite build` that day because the renderer had a typecheck error mid-edit. Rerun `dist:win` on a green tree |
| 2 | Unzip into a clean folder | Unverified. The unpacked folder was tested in place |
| 3 | `DeskTop.exe` opens and the backend is healthy | Done |
| 4 | First run shows the language pick, then KeySetup | Language pick seen. KeySetup Unverified |
| 5 | Full Demo Safe night with Wi-Fi off | Planned |
| 6 | Size recorded | Done, 327.1 MB zip |
| 7 | Secret scan | Done, see above |
| 8 | SHA-256 in `docs/delivery/submission-checklist.md` | Done 2026-11-04. Window close checked, no DeskTop.exe or python.exe left. Settings save checked in the packaged app |
| 9 | `backend.log` holds no key or token | Seen with no key set. Token redaction lives in `backend.ts` |
| 10 | Close the window and no `python.exe` is left | Unverified, see smoke result |
| 11 | Run on a machine or account without Python installed | Unverified |

## Known gaps

| Gap | Effect | Workaround |
|---|---|---|
| Unsigned | SmartScreen shows "Windows protected your PC" | More info, then Run anyway. See `docs/engineering/troubleshooting.md` |
| ffmpeg not bundled | No recording or replay reel | `winget install Gyan.FFmpeg`, or set `DESKTOP_FFMPEG` |
| Windows only | No Mac or Linux build | None |
| Large download | OpenCV, numpy, shapely and the Python runtime | Accepted |
| NSIS installer | `build:win` still builds it but it is untested | Use the zip |
| No Python audit | `pip-audit` is not configured | Known gap |
| Camera and mic untested in the packaged app | Permission handlers deny all by default | Unverified |
