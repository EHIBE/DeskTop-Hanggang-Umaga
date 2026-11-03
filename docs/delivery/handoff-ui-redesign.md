# DeskTop UI redesign handoff

2026-10-31 · EHIBE

## Summary

The renderer now looks like a pixel night game, and every screen shows one line of text in the language the player picked. All of it shipped in commit `1942e78` on main on 2026-10-31.

- **Language mode.** On first launch the player picks Filipino or English. After that, a FIL / ENG toggle on Start, KeySetup and Calibration switches the language live. The choice is saved in localStorage under `desktop.lang`.
- **Less text.** Before, the screens showed a Tagalog line with an English duplicate under it. Now each message shows one line only. 16 short copy keys were added for the new layouts.
- **New look.** A shared pixel night scene with a moon, trees, palms and a kubo. JRPG-style notched windows, beveled buttons, pixel icons, and a title-screen Start.
- **No backend, schema or dependency changes.** Typecheck, lint and prettier are clean.

## Screen by screen

Every screen sits on the fixed 1920x1080 stage. Main content is in a left column at x 160, and the night scene fills the background. Paths are under `app/src/renderer/src/`.

| Screen | File | What it shows now |
| --- | --- | --- |
| Language pick | `screens/LanguagePick.tsx` | New. Night scene, title, "Wika / Language", and two big buttons: Filipino and English. Shown when no language is saved yet |
| Connecting | `App.tsx` | The night scene, dimmed |
| KeySetup | `screens/KeySetup.tsx` | Title plus one window: a password field, a one-line privacy note with a lock icon, inline saved or invalid status, and Save / Play offline buttons |
| Start | `screens/Start.tsx` | Title screen. Window with the barrio name, a difficulty picker and a big Start Night button. A saves window on the right lists campaigns, each with a delete button you tap twice. Footer: tip, Demo Safe and SAM switches, language toggle. The cost meter bar was removed from this screen |
| Calibration | `screens/Calibration.tsx` | Sidebar window with a 3-step list (place, tap 4 corners, remove), camera buttons and width / height fields. The board sits in its own window |
| Night HUD | `screens/Night.tsx` | Same layout as before, now one caption line per message |
| Sunrise | `screens/Sunrise.tsx` | Three stepped dawn bands and a pixel sun rising. Title, win line, narration, replay, and the score panel on the right |
| Defeat | `screens/Defeat.tsx` | Dimmed night scene, fallen kubo, lose line, narration, replay, and the score panel |

## How the language mode works

One small store in `lib/lang.ts` holds the language, and every screen reads text through `say()`. Never read `.tl` or `.en` directly anymore.

- `lib/lang.ts` exports `Lang = 'tl' | 'en'`, `currentLang()` (defaults to `'tl'`), `langChosen()`, `setLang(lang)` and the `useLang()` hook. `useLang()` returns `null` until a language is saved. It is built on `useSyncExternalStore`, so every screen re-renders when the language changes.
- `lib/copy.ts` adds `say(key, params)`, which returns `t(key, params)[currentLang()]`, and `pick(entry)` for `{tl, en}` objects that come from the backend.
- `App.tsx` shows `LanguagePick` while `useLang() === null`, before Connecting. The cost and Demo Safe chips render only once a language is set.
- `Night.tsx` imports `pick as pickText`, because Night already has its own local `pick` callback.
- Narration picks `narration_en` or `narration_tl` from `currentLang()`. UnitCard text follows the language too, and its "EN:" line is gone.
- `components/Bilingual.tsx` still exists for old call sites, but it now renders a single `caption-tl` line.
- `components/LangToggle.tsx` is the FIL / ENG radiogroup. Drop it on any screen.

To add text, use the `desktop-add-copy-key` skill. Add the key to `lib/copy.ts` with both `tl` and `en`, add a row to `docs/design/copy-deck.md` (now 245 keys), then call `say('your.key')`.

## Design system pieces

All component CSS lives in `assets/main.css` inside `@layer components`. If you add a class outside that layer, it will override Tailwind utilities again. That bug is why text sizes were ignored before.

| Piece | Where | Notes |
| --- | --- | --- |
| `.window` | `main.css` | JRPG panel with notched corners from `clip-path`. Use it for any boxed content. `.panel` is the plainer box |
| `.btn` and its variants | `main.css` | Beveled with inset shadows and a pressed state. Variants: `.btn-primary`, `.btn-big`, `.btn-quiet` (footer switches, reads `aria-checked`), `.btn-danger` (red when `data-armed`) |
| `.segmented`, `.lang-toggle` | `main.css` | Radio button groups. Selection is driven by `aria-checked` |
| `.menu-row`, `.menu-cursor` | `main.css` | Save list rows. On hover or focus, an arrow cursor nudges in |
| `.field`, `.label` | `main.css` | Text input and its label. Placeholder text is mist at 0.6 opacity |
| `.title-mark`, `.title-sub` | `TitleMark.tsx` | The "DeskTop" logo and its sub line, in `large` or `small` size |
| `.step` with `data-state` | `Calibration.tsx` | Step list states: `todo`, `active`, `done` |
| `.rise-in` | `main.css` | Entry animation. Stagger it with `animationDelay` |
| `PixelIcon` | `components/PixelIcon.tsx` | SVG grid icons: arrow, check, cross, lock, play, moon, sun, trash, camera, wifi. Takes `size` (pixel scale) and `className`, and draws in `currentColor` |
| `NightScene` | `components/NightScene.tsx` | Memoised background: seeded stars, pixel moon, two canopy layers, three palms, a kubo with a flickering window, fireflies, ground strip. Pass `dim` for result or loading screens |

Rules that still apply:

- Only the locked 16-colour Gabi palette (`lib/palette.ts`, `gabi-*` classes).
- Press Start 2P font only.
- Pixel art is SVG with `shapeRendering="crispEdges"`.
- The reduced-motion block in `main.css` turns off every new animation. Add new animations there too.
- `docs/design/DESIGN.md` covers the language mode, windows, icons, scene and the layer rule.

## Verified and not yet verified

Two screens were checked in the running app with screenshots. Five were only typechecked, so look at those first.

| Screen or check | Status | How it was checked |
| --- | --- | --- |
| Language pick | Verified | Screenshot in the live app |
| Start, FIL and ENG | Verified | Screenshots. The toggle switches live, and Start Night enables once a name is typed |
| Typecheck, renderer lint, prettier | Verified | `npm --prefix app run typecheck` and `lint`. Clean |
| KeySetup | Not checked | A key was already stored, so the screen never showed |
| Calibration | Not checked | Skipped to avoid creating campaign data |
| Night HUD | Not checked | Needs a running night |
| Sunrise | Not checked | Needs a won night |
| Defeat | Not checked | Needs a lost night |

Things to watch for on those screens: text that overflows a `.window`, buttons that wrap to two lines in English, and the right-hand score panel overlapping the left column on Sunrise and Defeat.

## How to run and screenshot

Run `npm --prefix app run dev` from the repo root to play it. To capture screenshots without clicking, start it with remote debugging on and drive it over CDP.

1. From `app/`, run `npx electron-vite dev --remoteDebuggingPort 9333`.
2. Run the screenshot script with Node 22 or newer: `node shot.mjs out.png "<js expression>"`. It sets the viewport to 1600x900, evaluates the optional expression in the page, waits 1.2 s, then saves a PNG.
3. To get the first-run screen back, evaluate `localStorage.removeItem('desktop.lang'); location.reload()`.

The script was in the session scratchpad, not the repo. Here is the whole thing:

```js
import { writeFileSync } from 'node:fs'
const [, , out, expr] = process.argv
const list = await (await fetch('http://127.0.0.1:9333/json')).json()
const page = list.find((p) => p.type === 'page')
const ws = new WebSocket(page.webSocketDebuggerUrl)
let id = 0
const pending = new Map()
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) } }
await new Promise((r) => (ws.onopen = r))
const call = (method, params = {}) => new Promise((resolve) => { id += 1; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })) })
await call('Emulation.setDeviceMetricsOverride', { width: 1600, height: 900, deviceScaleFactor: 1, mobile: false })
if (expr) { await call('Runtime.evaluate', { expression: expr, awaitPromise: true }); await new Promise((r) => setTimeout(r, 1200)) }
const shot = await call('Page.captureScreenshot', { format: 'png' })
writeFileSync(out, Buffer.from(shot.result.data, 'base64'))
ws.close()
```

## Open items, gotchas and constraints

The redesign is done. What is left is checking it by eye and getting the new copy reviewed.

- [ ] Look at KeySetup, Calibration, Night HUD, Sunrise and Defeat in the running app, in both FIL and ENG
- [ ] Have playtesters review the 16 new copy lines. They are marked Proposed in `docs/design/copy-deck.md`
- [ ] Run the `desktop-cultural-reviewer` agent on the new Taglish lines (`lang.*`, `title.sub`, `start.tip`, `calib.step_*`)
- [x] `MVP_BUILD_PROMPT.md` kept as history in `docs/prompts/archive/` (2026-11-03)

Gotchas:

- `app/electron.vite.config.ts.*.mjs` is a temp file from electron-vite. It is untracked, it causes the only lint warnings, and it should not be committed.
- When you generate SVG paths in NightScene, guard every `sqrt` with `Math.max(0, ...)`. A single `NaN` stops SVG path parsing partway across the screen.
- If a Python script writes files on Windows, use `newline='\n'`. Otherwise prettier flags CRLF line endings.
- The cost meter is no longer on Start. It still shows as a chip in `App.tsx` once a language is set.

Project rules from `CLAUDE.md` that apply here: never read `backend/.env`. Keep the API key out of the renderer. No new dependencies without approval. No code comments. Commit messages use `type: Action item` with EHIBE as sole author. No push, branch or amend.
