---
title: Release and packaging
purpose: How to produce the pre-built unsigned Windows zip with the Python backend bundled, and how to check it before release
read_when: [building the release zip, changing electron-builder.yml, fixing a packaged-build bug, preparing the submission download]
canonical_for: [release artifact, packaging plan, Electron fuses plan, release checklist]
sources: [app/package.json, app/electron-builder.yml, app/src/main/backend.ts, app/src/main/index.ts, backend/requirements.txt, docs/engineering/setup-windows.md, docs/how-to-run.md]
status: planned
last_verified: 2026-11-03
related: [docs/how-to-run.md, docs/engineering/setup-windows.md, docs/engineering/troubleshooting.md, docs/delivery/submission-checklist.md, docs/delivery/live-api-runbook.md]
---

# Release and packaging

The release is an unsigned zip of the unpacked Windows app with the Python backend and its venv inside, so a player can run it without installing Node or Python. None of this is built yet. Every step below is Planned or Unverified until someone runs it.

## Key facts

| Fact | Value |
|---|---|
| Target artifact | Unsigned zip of the electron-builder `dir` output. NSIS installer is optional |
| Status | Planned. No packaged build has been run |
| Platform | Windows only. The `build:mac` and `build:linux` scripts exist but are not supported |
| Build command | `npm --prefix app run build:unpack` (runs typecheck, `electron-vite build`, `electron-builder --dir`) |
| Installer command | `npm --prefix app run build:win` (NSIS, `${name}-${version}-setup.exe`) |
| App id | `com.ehibe.desktop`, product name `DeskTop`, executable `DeskTop` |
| Backend location when packaged | `process.resourcesPath/backend` (from `backendDir()` in `app/src/main/index.ts`) |
| Python the app launches | `<backendDir>/.venv/Scripts/python.exe` |
| Signing | None. SmartScreen will warn |
| ffmpeg | Not bundled. Replay and recording need it on PATH or `DESKTOP_FFMPEG` |

## What the current config does

Canonical: `app/electron-builder.yml`.

- It sets `appId`, `productName`, `win.executableName` and an NSIS block.
- It has no `extraResources`, so the backend is not copied into a packaged build. A packaged app would fail to start the backend.
- It has no signing and no fuses.
- `asarUnpack` lists `resources/**`.
- `npmRebuild` is false.

## What must be bundled

| Item | Source | Rule |
|---|---|---|
| Backend source | `backend/` | Copy `*.py` and the package folders (`capture`, `db`, `game`, `gm`, `replay`, `rules`, `vision`, `voice`). Include `db/schema.sql` |
| Backend exclusions | `backend/tests`, `backend/smoke`, `__pycache__`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`, `.coverage`, `.env` | Never ship `.env`. Tests and smoke scripts are not needed at runtime |
| Python runtime | `backend/.venv` or an embeddable Python | Must be at `resources/backend/.venv/Scripts/python.exe` because the app hardcodes that path |
| Assets | `assets/` (fonts, `lines.json`, `palette.json`, `sfx`, `sprites`, `tiles`) | Unverified: how the backend finds `assets/` when packaged. Verify by running the zip, see the checklist |
| Renderer and main | `app/out` | Produced by `electron-vite build` |

The venv holds absolute paths in its launcher scripts and `pyvenv.cfg`, which point at the Python that built it. Unverified: whether a copied venv runs on a machine without that Python. Verify in step 3 of the checklist on a clean machine or a clean user account. If it fails, switch to an embeddable Python plus `pip install --target`.

## Planned extraResources mapping

Planned change to `app/electron-builder.yml`. Not applied.

```yaml
extraResources:
  - from: ../backend
    to: backend
    filter:
      - '**/*'
      - '!tests/**'
      - '!smoke/**'
      - '!**/__pycache__/**'
      - '!.env'
      - '!.mypy_cache/**'
      - '!.ruff_cache/**'
      - '!.pytest_cache/**'
```

- Result: `resources/backend` next to `app.asar` in the unpacked folder.
- Check the `filter` globs against the electron-builder docs when applying. Unverified.
- Add a second entry for `../assets` if the backend reads assets from a sibling folder. Unverified.

## Packaged origin issue

Canonical code: `app/src/main/index.ts` (`FILE_ORIGINS`, `allowedOrigins()`) and `backend/server.py` (the `/ws` origin check).

- In a packaged build the renderer loads from `file://`. `allowedOrigins()` returns `['file://']`.
- The backend closes the socket with code 1008 unless the `Origin` header is in `DESKTOP_ALLOWED_ORIGINS`.
- Chromium sends the Origin of a `file://` page as the string `null`, not `file://`. Status: Unverified, believed true.
- Fix (ADR-0111, done 2026-11-03): main sets `DESKTOP_PACKAGED=1` when `app.isPackaged`. Only then `websocket_origins` in `backend/server.py` adds `null` to the allow-list. The token check still gates every connection. Dev builds still refuse `null`. Tests in `backend/tests/test_server.py`.
- Verify by running the unpacked app and watching `backend.log` for "rejected websocket from an unexpected origin". The UI will sit on Connecting if it fails.

## Planned Electron fuses

Set through the electron-builder `electronFuses` config. No new dependency (decision of 2026-11-03). Status: Planned. Not applied.

| Fuse | Setting |
|---|---|
| RunAsNode | Off |
| EnableNodeOptionsEnvironmentVariable | Off |
| EnableNodeCliInspectArguments | Off |
| EnableEmbeddedAsarIntegrityValidation | On |
| OnlyLoadAppFromAsar | On |
| EnableCookieEncryption | On |

- Unverified: exact key names in `electronFuses` for electron-builder 26. Check the electron-builder docs before editing.
- `OnlyLoadAppFromAsar` is compatible with `extraResources` because the backend sits outside the asar.
- The backend is spawned with `child_process.spawn` of `python.exe`, not with Electron as Node, so RunAsNode off does not affect it. Verify in step 3 of the checklist.

## Build steps

All Planned. Run from the repo root in PowerShell.

1. Confirm a clean tree and green checks: `backend\.venv\Scripts\python -m pytest backend/tests -q`, `npm --prefix app run typecheck`, `npm --prefix app run lint`.
2. Apply the `extraResources` and fuses changes above.
3. Build: `npm --prefix app run build:unpack`.
4. Find the output folder under `app\dist`. The exact name is Unverified until the first build.
5. Delete any `.env` found inside the output. Confirm none exists.
6. Zip the unpacked folder, for example `Compress-Archive -Path app\dist\win-unpacked\* -DestinationPath DeskTop-1.0.0-win.zip`. Adjust the folder name to the real output.
7. Record the SHA-256: `Get-FileHash DeskTop-1.0.0-win.zip -Algorithm SHA256`.

## Release checklist

| # | Check | Status |
|---|---|---|
| 1 | Build runs without errors | Planned |
| 2 | Unzip into a clean folder, for example `C:\Temp\DeskTop-test` | Planned |
| 3 | Run `DeskTop.exe`. The window opens and the backend reaches healthy within 20 s | Planned |
| 4 | First run shows the language pick, then KeySetup. Paste a test key or choose Demo Safe Mode | Planned |
| 5 | Play a full Demo Safe night with Wi-Fi off | Planned |
| 6 | Size check: record the zip size in MB. No target is set | Planned |
| 7 | Secret scan of the zip contents: no `.env`, no `model-key.bin`, no `*.sqlite`, no string matching the key | Planned |
| 8 | Record the zip SHA-256 in `docs/delivery/submission-checklist.md` | Planned |
| 9 | `backend.log` appears under `%APPDATA%\DeskTop\logs` and holds no key or token | Planned |
| 10 | Close the window. No `python.exe` child is left running | Planned |

For the secret scan, extract the zip and search the tree with `Select-String` for the key prefix the owner knows. Do not paste the key into any tool output.

## Known gaps

| Gap | Effect | Workaround |
|---|---|---|
| Unsigned | SmartScreen shows "Windows protected your PC" | Click More info, then Run anyway. See `docs/engineering/troubleshooting.md` |
| ffmpeg not bundled | No recording or replay reel | `winget install Gyan.FFmpeg`, or set `DESKTOP_FFMPEG` |
| Windows only | No Mac or Linux build is supported | None |
| Large download | The venv carries OpenCV, numpy and more | Accepted |
| No Python audit | `pip-audit` is not configured | Known gap |
| Camera and mic untested in the packaged app | Permission handlers deny all by default | Unverified. Check in step 3 of the checklist |
