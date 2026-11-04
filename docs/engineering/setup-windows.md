---
title: Windows setup
purpose: Exact steps to get a working dev environment on Windows from the current repo state
read_when: [first setup, broken environment, onboarding an agent to run code]
canonical_for: [dev setup steps, prerequisites, run commands, current setup gaps]
sources: [docs/DeskTop_PRD.md#project-setup-and-folder-structure, docs/DeskTop_Build_Guide.md#02-install-tools-windows, app/package.json, backend/requirements.txt]
status: active
last_verified: 2026-11-04
related: [docs/engineering/environment-and-config.md, docs/decisions/ADR-0101-python-env-and-pins.md, docs/decisions/ADR-0102-wire-tailwind.md]
---

# Windows setup

These steps take a fresh Windows machine to a running app and backend. The venv, pins and Tailwind are already set up in the repo.

## Key facts

| Fact | Value |
|---|---|
| Repo path | `C:\Users\ADMIN\Documents\Projects\Hackathon\DeskTop-Hanggang-Umaga` |
| Prerequisites | Git, Node.js 20.19+ or 22.12+ (the Vite 8 and electron-vite 6 engine range, CI uses 22), Python 3.13 (`py -3.13`, ADR-0101), ffmpeg on PATH or `DESKTOP_FFMPEG` (recording and replay only), VS Code with Python and ESLint |
| Backend port | A free port on 127.0.0.1 picked by Electron each launch. 8765 only for a manual backend run |
| Gaps today | ffmpeg not on PATH (B14, Manual: EHIBE). Venv, pins and Tailwind done 2026-10-28 |
| Release zip | `npm --prefix app run dist:win`, then zip `app\dist\win-unpacked`. Canonical: `docs/delivery/release-and-packaging.md` |

## Check tools (PowerShell)

| Tool | Check |
|---|---|
| Git | `git --version` |
| Node.js | `node -v` (20.19+ or 22.12+) |
| Python | `py -3.13 --version` (3.10+ needed by meta-sam-parser) |
| ffmpeg | `ffmpeg -version` |

## Frontend

```powershell
npm --prefix app install
npm --prefix app run dev
```

A window opens. Tailwind is already wired (ADR-0102).

## Backend (ADR-0101)

```powershell
py -3.13 -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
```

- `requirements.txt` holds the exact pins (ADR-0101). Never regenerate it with `pip freeze` without approval.
- It installs `opencv-contrib-python` only. Never also install `opencv-python`. The tracker uses KCF from the contrib build.

## Key for development

- Put the key after `MODEL_API_KEY=` in `backend\.env` (git-ignored). Never commit it, never paste it in chat or docs.
- In the shipped app the key comes from Electron safeStorage instead.
- `DESKTOP_GLIMMER_URL` works only in `backend\.env`, which the backend reads only when `DESKTOP_DEV=1`. Electron does not pass it through, so the zip cannot use Glimmer. `DESKTOP_FFMPEG` is passed through from the shell. Canonical: `docs/engineering/environment-and-config.md`.

## Run the backend

The backend needs a token of at least 32 characters and uses the app factory. From the repo root in PowerShell:

```powershell
cd backend
$env:DESKTOP_TOKEN = -join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
$env:DESKTOP_DEV = "1"
.venv\Scripts\python -m uvicorn server:create_app_from_env --factory --host 127.0.0.1 --port 8765
```

Check health in a second window: `Invoke-RestMethod -Uri http://127.0.0.1:8765/health -Headers @{ 'X-Desktop-Token' = $env:DESKTOP_TOKEN }`. Expect `ok : True`. Details: `docs/engineering/troubleshooting.md#run-the-backend-by-hand`.

## Physical setup

- Plain matte mat, about 60 x 40 cm clear
- Camera 45 to 70 cm above the desk, looking straight down (stand, clamp, or phone as webcam)
- One A4 sheet, even lamp light
- Demo objects: mug, coin, keys, pen, eraser (no identical pairs)

## Quality commands

| Task | Command |
|---|---|
| Typecheck | `npm --prefix app run typecheck` |
| Lint | `npm --prefix app run lint` |
| Format | `npm --prefix app run format` |
| Audit | `npm --prefix app audit` |
| Tests | `backend\.venv\Scripts\python -m pytest backend/tests -q` |

## Notes from the PRD setup script

- In cmd.exe, a typed `for` uses `%d`, in a `.bat` file `%%d`.
- The PRD Part 2 script overwrites starter files. Do not rerun it on this repo.
