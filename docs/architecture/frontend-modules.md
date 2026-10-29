---
title: Frontend modules
purpose: Electron main, preload and renderer structure with responsibilities and current scaffold state
read_when: [creating or changing any file under app/]
canonical_for: [frontend module responsibilities, Electron process roles, renderer folder map]
sources: [docs/DeskTop_PRD.md#project-setup-and-folder-structure, app/src/main/index.ts, app/src/preload/index.ts, app/package.json, app/electron.vite.config.ts]
status: active
last_verified: 2026-10-29
related: [docs/architecture/overview.md, docs/engineering/security-and-privacy.md, docs/design/hud-components.md]
---

# Frontend modules

The app is an electron-vite React TypeScript project. Main spawns the backend and holds the key, preload passes only the port and token, and the renderer draws the board and HUD.

## Key facts

| Fact | Value |
|---|---|
| Tooling | Electron ^44.7.2, electron-vite ^6.0.0, Vite ^8.3.4, React ^19.3.0, TypeScript ^5.9.3 (noImplicitAny on), Tailwind ^4.3.3 (wired, devDependency) |
| Lint and format | ESLint ^9.39.5 flat config, Prettier (singleQuote, no semi, width 100) |
| Alias | `@renderer` to `src/renderer/src` |
| Exists today | `main/index.ts`, `main/backend.ts` (spawn, free port, health, restart), `main/keystore.ts` (safeStorage), preload `getConfig`, `getKeyStatus`, `saveKey`, `showReel`. Renderer: `lib/types.ts`, `lib/socket.ts`, `lib/copy.ts`, `lib/palette.ts`, `canvas/Board.tsx`, `components/Stage.tsx`, `components/Bilingual.tsx`, screens KeySetup, Start, Calibration (M3), then Summon, UnitCard, VoiceClaim, Night, Sunrise, Defeat, and hud TopBar, UnitStrip, OrderChips, TapMenu, Narration, Captions, VoiceControls (M4 to M11) |

## Process roles

| Process | Files | Responsibility |
|---|---|---|
| Main | `src/main/index.ts`, `backend.ts`, `keystore.ts` | Window, spawn and restart backend with key and token in env, safeStorage key, health check, restart on crash |
| Preload | `src/preload/index.ts`, `index.d.ts` | Expose `getConfig`, `getKeyStatus`, `saveKey` and `showReel` only. The key is never returned |
| Renderer | `src/renderer/src/**` | Screens, canvas board, HUD, WebSocket client, copy |

## Renderer map

| Folder or file | Responsibility |
|---|---|
| `main.tsx` | Mount React in StrictMode |
| `App.tsx` | Screen router driven by backend state |
| `lib/socket.ts` | WebSocket client with token, reconnect, typed messages |
| `lib/copy.ts` | All Taglish and English text by copy key |
| `lib/types.ts` | Unit, Enemy, Event, Intent, message types (mirror Pydantic) |
| `canvas/Board.tsx` | Draw desk feed and sprites |
| `canvas/sprites.ts` | Sprite loading, integer scaling |
| `canvas/rings.ts` | Move rings and ghosts |
| `canvas/arrows.ts` | Enemy intent arrows |
| `hud/TopBar.tsx` | Turn, phase, kubo HP, banners, REC |
| `hud/UnitStrip.tsx` | HP and cooldowns |
| `hud/Captions.tsx` | Live transcript with speaker label. Narration lives in `hud/Narration.tsx` |
| `hud/VoiceControls.tsx` | Mic status, open or push-to-talk switch, hold Space or the hold button, Voice problems retry |
| `hud/OrderChips.tsx` | Order chips |
| `hud/SpeakerChip.tsx` | Not built. The speaker label shows inline in captions and voice chips |
| `hud/TapMenu.tsx` | Tap controls (FR-25) |
| `screens/*.tsx` | Start, KeySetup, Calibration, Summon, UnitCard, VoiceClaim, Night, Sunrise, Defeat. Replay lives in `components/ReplayPanel.tsx` on Sunrise and Defeat. Settings is a Could and not built |

## Scaffold gaps (fixed 2026-10-28, ADR-0102, ADR-0103, ADR-0108)

| Gap | Fix |
|---|---|
| `sandbox: false` | `sandbox: true`, `contextIsolation: true`, `nodeIntegration: false` |
| Preload exposes full `electronAPI` | Expose only `{ port, token }` |
| `shell.openExternal` on any URL | Allowlist https URLs |
| `ipcMain.on('ping')` test handler | Remove |
| Tailwind not wired | Add `tailwindcss()` to renderer plugins and `@import "tailwindcss"` in main.css |
| Window title "Electron", productName "app" | Rename to DeskTop |
| CSP lacks backend connect-src | Add `connect-src 'self' ws://127.0.0.1:8765 http://127.0.0.1:8765` |

## Rules

- No Node APIs in the renderer. No `dangerouslySetInnerHTML`.
- The renderer never sees the API key.
- All text comes from `lib/copy.ts`.
- Function components with explicit return types (`React.JSX.Element`).
- Typecheck with `npm --prefix app run typecheck`. Lint with `npm --prefix app run lint`.
