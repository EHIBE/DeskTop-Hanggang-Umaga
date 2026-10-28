---
title: Windows setup
purpose: Exact steps to get a working dev environment on Windows from the current repo state
read_when: [first setup, broken environment, onboarding an agent to run code]
canonical_for: [dev setup steps, prerequisites, run commands, current setup gaps]
sources: [docs/DeskTop_PRD.md#project-setup-and-folder-structure, docs/DeskTop_Build_Guide.md#02-install-tools-windows, app/package.json, backend/requirements.txt]
status: active
last_verified: 2026-10-28
related: [docs/engineering/environment-and-config.md, docs/decisions/ADR-0101-python-env-and-pins.md, docs/decisions/ADR-0102-wire-tailwind.md]
---

# Windows setup

The scaffold commit exists, but the Python venv is missing and requirements are empty. These steps reach a running app and backend from today's repo state.

## Key facts

| Fact | Value |
|---|---|
| Repo path | `C:\Users\ADMIN\Documents\Projects\Hackathon\DeskTop-Hanggang-Umaga` |
| Prerequisites | Git, Node.js 20+, Python 3.13 (`py -3.13`, ADR-0101), ffmpeg on PATH (needed from Phase 13), VS Code with Python and ESLint |
| Backend port | 8765 on 127.0.0.1 |
| Gaps today | ffmpeg not on PATH (Manual: EHIBE before Phase 13). Venv, pins and Tailwind done 2026-10-28 |

## Check tools (PowerShell)

| Tool | Check |
|---|---|
| Git | `git --version` |
| Node.js | `node -v` (20 or newer) |
| Python | `py -3.13 --version` (3.10+ needed by meta-sam-parser) |
| ffmpeg | `ffmpeg -version` |

## Frontend

```powershell
npm --prefix app install
npm --prefix app run dev
```

A window opens. Then wire Tailwind (ADR-0102): add `import tailwindcss from '@tailwindcss/vite'` and `tailwindcss()` to the renderer `plugins` in `app/electron.vite.config.ts`, and `@import "tailwindcss";` at the top of `app/src/renderer/src/assets/main.css`.

## Backend (needs approval, ADR-0101)

```powershell
py -3.13 -m venv backend\.venv
backend\.venv\Scripts\python -m pip install --upgrade pip
backend\.venv\Scripts\python -m pip install fastapi "uvicorn[standard]" websockets openai opencv-contrib-python numpy pillow shapely pydantic sounddevice meta-sam-parser python-dotenv rapidfuzz pytest
backend\.venv\Scripts\python -m pip freeze > backend\requirements.txt
```

- Install `opencv-contrib-python` only. Never also `opencv-python`. The contrib build has CSRT and KCF.
- After that, a fresh machine installs with `backend\.venv\Scripts\python -m pip install -r backend\requirements.txt`.

## Key for development

- Put the key after `MODEL_API_KEY=` in `backend\.env` (git-ignored). Never commit it, never paste it in chat or docs.
- In the shipped app the key comes from Electron safeStorage instead.

## Run the backend

```powershell
cd backend
.venv\Scripts\python -m uvicorn server:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/health` and expect `{"ok": true}`.

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
