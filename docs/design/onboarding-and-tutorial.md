---
title: Onboarding and tutorial
purpose: Design spec for four features approved 2026-11-03 - first-night hints, folklore glossary, speaker chip and synthesized sound
read_when: [building or reviewing hints, the glossary panel, the speaker chip or sound effects, writing the copy keys for them]
canonical_for: [first-night hint rules, glossary panel behavior, speaker chip look, synthesized sound cue recipes, sound mute setting]
sources: [docs/design/cultural-care.md, docs/design/hud-components.md, docs/design/audio.md, docs/design/screens.md, docs/design/DESIGN.md, app/src/renderer/src/screens/Night.tsx, app/src/renderer/src/lib/lang.ts]
status: draft
last_verified: 2026-11-03
related: [docs/product/user-journey.md, docs/design/accessibility.md, docs/design/copy-deck.md, docs/game/enemies.md]
---

# Onboarding and tutorial

Four small features make the first night easier to learn and nicer to hear, with no new dependency and no audio files. This file is the spec. Nothing here is built yet and every copy line is Proposed and needs cultural review.

## Key facts

| Fact | Value |
|---|---|
| Features | (a) first-night hints, (b) folklore glossary, (c) speaker chip, (d) synthesized sound |
| Freeze | New features end Nov 3 6:00 PM SGT. These four are approved |
| Stage | 1920x1080, scaled by `components/Stage.tsx` |
| Parts allowed | Gabi 16 tokens, `.window`, `.panel`, `.banner`, `.btn`, `.btn-quiet`, `PixelIcon`, `LangToggle`. No new component library |
| Storage | localStorage only, always in try/catch, page works with it empty |
| New keys | `desktop.tutorial`, `desktop.sound` (existing: `desktop.lang`) |
| Copy | New keys in `lib/copy.ts` with tl and en. Rules: `docs/design/copy-deck.md` and skill `desktop-add-copy-key` |
| Review | Every new line goes to 2 Filipino reviewers before recording. Agent: `desktop-cultural-reviewer` |
| Not in scope | Settings screen (skipped), TTS, footstep cues, music |

## A. First-night hints

### Purpose

Teach the turn loop in the first three turns of a campaign without a separate tutorial screen. One line at a time, never blocking.

### Placement

- A `.banner` strip above the captions row in `screens/Night.tsx`, same width as the captions row, height 48 px, one line, 24 px text.
- The strip sits below the board so it never covers sprites, rings or arrows.
- A `PixelIcon` `arrow` in lantern leads the line. A `.btn-quiet` with `PixelIcon` `cross` dismisses it. Tap target at least 48 px.

### Hint list

| Key | Shown when | Why |
|---|---|---|
| `tut.telegraph` | Turn 1, phase PLAYER_PHASE begins | Arrows are the core promise (no dice) |
| `tut.move` | Turn 1, after `tut.telegraph` is dismissed or 8 s pass | Teach rings |
| `tut.order` | Turn 1, after `tut.move` is dismissed or 8 s pass | Teach voice and tap |
| `tut.end_turn` | Turn 1, once one order chip exists, or at turn 2 start | Teach finish |
| `tut.push` | Turn 3 when a tikbalang is telegraphed (Normal teaches it on turn 3) | Teach the ghost outline |

- Turn 2 shows only hints not yet seen. If all four were seen, turn 2 shows none.
- On Madali or Mahirap the tikbalang may arrive on another turn. Show `tut.push` on the first tikbalang telegraph within turns 1 to 3 only. Verify wave timing in `docs/game/waves-and-difficulty.md`.
- Never show a hint in PAUSED, END_TURN_SNAPSHOT or any resolve phase.

### Proposed copy (need cultural review)

| Key | tl | en |
|---|---|---|
| `tut.telegraph` | Ang pulang palaso ay ang tatamaan nila ngayong turn. | Red arrows show who they will hit this turn. |
| `tut.move` | Ilipat ang tunay na gamit. Berde ang singsing kung abot. | Slide a real object. A green ring means it can reach. |
| `tut.order` | Sabihin o i-tap ang utos. Halimbawa: "Stapler, atake ang aswang!" | Say or tap an order. For example: "Stapler, atake ang aswang!" |
| `tut.end_turn` | Kapag handa na, sabihin ang "Tapos na" o pindutin ang TAPOS. | When ready, say "Tapos na" or press End Turn. |
| `tut.push` | Maaaring itulak ng tikbalang ang gamit mo. Ilipat ito sa anino. | A tikbalang can shove a unit. Slide it onto the ghost outline. |
| `tut.dismiss` | Sige | Got it |
| `tut.skip_all` | Laktawan lahat | Skip all hints |

- The Taglish example in `tut.order` is the same phrase used in `docs/how-to-run.md`.
- `tut.push` describes the behavior already in the game. Wording avoids saying a tikbalang "attacks", per the respect rules.

### States

| State | Shows |
|---|---|
| Hidden | Not turns 1 to 3, already seen, skipped, or not a PLAYER_PHASE |
| Showing | Banner with arrow icon, one line in the chosen language, dismiss button |
| Dismissed | Strip removed, next hint in the chain may show |
| Skipped all | Strip removed, all five hints marked seen |
| Demo Safe | Same hints. `tut.order` swaps to the tap-only wording if voice is off (key `tut.order_tap`, Proposed) |

### Storage

- Key `desktop.tutorial`. Value is JSON: `{ "<campaign_id>": ["tut.telegraph", "tut.move"] }`. Ids of seen hints per campaign.
- Shown once per campaign. A new campaign shows hints again. Continue on a campaign that has seen them shows none.
- Read failure or corrupt JSON counts as "not seen". Write failure is ignored, hints may repeat next launch.

### Accessibility

- Banner is `role="status"` with `aria-live="polite"`. It never takes focus.
- Dismiss button has `aria-label` from `tut.dismiss`.
- Reduced motion: when `prefersReducedMotion()` is true the strip appears with no slide or pulse. Otherwise one 200 ms fade, no loop.
- Contrast: moon text on night fill (the HUD default). Do not rely on colour. The arrow icon plus the text carry meaning.
- Hints disappear on dismiss or on the next phase change. They never delay End Turn or any input.

### Acceptance checks

- [ ] Fresh campaign shows `tut.telegraph` at turn 1 PLAYER_PHASE. Ends with `tut.end_turn`.
- [ ] Dismissed hint does not return after relaunch and Continue.
- [ ] A second new campaign shows hints again.
- [ ] No hint appears at turn 4 or later.
- [ ] `tut.push` shows only when a tikbalang is telegraphed.
- [ ] With storage blocked the Night screen still renders.
- [ ] With reduced motion on, no animation runs.
- [ ] Strip does not cover the board, chips, or End Turn.
- [ ] Both languages fit on one line at 1920x1080. Shorten the copy if not.

## B. Folklore glossary

### Purpose

Give players who do not know the creatures a respectful one-line meaning for each term, in the game, offline. Source of wording: `docs/design/cultural-care.md` (canonical for the glossary).

### Placement

- A `.window` panel centered on the stage, 960 px wide, max height 800 px, list scrolls inside.
- Entry points: a `.btn-quiet` "Folklore" button in the Start footer beside the Demo Safe switch and `LangToggle`, and a `.btn` in the Night pause overlay (PAUSED phase) beside Resume.
- Not available in other night phases, so it cannot cover the board during play.
- Close button `.btn` at the bottom. Escape also closes it.

### Terms

Descriptions reuse the cultural-care wording word for word. Keep them in sync with that file.

| Key | Term | en description (verbatim from cultural-care.md) |
|---|---|---|
| `gloss.aswang` | Aswang | A shape-shifting night creature in Philippine folklore that hunts people who wander alone |
| `gloss.tikbalang` | Tikbalang | A tall creature with a horse's head that leads travelers astray in forests and mountains |
| `gloss.kapre` | Kapre | A big tree giant that sits in large trees like the balete and smokes a huge cigar |
| `gloss.manananggal` | Manananggal | A creature that splits its upper body from its lower half and flies at night. Salt on the lower half stops it from rejoining |
| `gloss.duwende` | Duwende | A small spirit that lives in mounds (punso) and can bring luck or mischief. People say "tabi tabi po" to ask permission to pass |
| `gloss.albularyo` | Albularyo | A traditional folk healer |
| `gloss.anting` | Anting-anting | An amulet believed to give protection |
| `gloss.kubo` | Bahay kubo | A traditional Filipino house made of bamboo and nipa |

- Title key `gloss.title`: tl "Mga Alamat" (Proposed), en "Folklore" (Proposed). Close key `gloss.close`: tl "Isara", en "Close".
- Tagalog versions of the eight descriptions are Pending. A Filipino reviewer writes them, `desktop-cultural-reviewer` checks them. Until then the panel shows the English line under both languages. Do not machine-translate folklore.
- Kapre stays in the list even though Kapre smoke is cut from play, because the creature may be seen in art. Verify against `docs/game/enemies.md` before ship and drop it if no kapre appears.
- No place names, no region claims, no gore, per the cultural-care rules.

### Layout

- Each row: term in lantern 24 px, description in moon 16 px below it. Rows separated by a 2 px dusk line. Use `.menu-row` styling without the cursor.
- No icons per term in v1. `PixelIcon` is used only for the close cross.

### States

| State | Shows |
|---|---|
| Closed | Nothing. Focus returns to the button that opened it |
| Open | Eight rows, first term focused, scroll if needed |
| Open during pause | Pause overlay stays behind. Resume is disabled until the panel closes |

### Accessibility

- `role="dialog"`, `aria-modal="true"`, `aria-labelledby` the title.
- Focus is trapped inside. Tab order: terms list then Close.
- Rows are plain text, no hidden meaning in colour.
- Works with the FIL / ENG toggle already on screen.

### Acceptance checks

- [ ] Button on Start opens the panel with all 8 terms.
- [ ] Button in the Night pause overlay opens it. No button during a live turn.
- [ ] Each English line matches `docs/design/cultural-care.md` exactly.
- [ ] Escape and Close return focus to the opener.
- [ ] Panel works offline and in Demo Safe.
- [ ] Two Filipino reviewers sign off in `docs/playtests.md` before recording.

## C. Speaker chip

### Purpose

Show which player spoke, so overlap, "Hindi" cancels and claims are clear. This is the component marked "Not built" in `docs/design/hud-components.md`.

### Look

- A small chip, 32 px high, `.panel` fill, 2 px border in the player colour.
- Content: a shape icon then the label P1 to P4.
- Colour is never the only signal. Each player also has a shape, drawn as a 12 px pixel glyph inside the chip.

| Label | Colour token | Shape |
|---|---|---|
| P1 | `gabi-lantern` | Circle |
| P2 | `gabi-dahon` | Square |
| P3 | `gabi-bukang` | Triangle |
| P4 | `gabi-mist` | Diamond |

- Shapes are drawn with a small inline pixel grid in the same style as `PixelIcon`. If `PixelIcon` is extended it needs four new glyphs. Contrast of each colour on `gabi-night` Unverified. Check with a contrast tool and swap tokens if under 4.5:1.

### Placement

- In `hud/Captions.tsx`, replacing the plain lantern "speaker:" text before each caption line.
- In `hud/OrderChips.tsx`, at the start of each chip that has a speaker, replacing the trailing speaker text.
- On `VoiceClaim`, beside each player entry so players learn their mark.

### States

| State | Shows |
|---|---|
| Speaking | Chip pulses once per second while a partial caption is live |
| Final | Chip steady with the final caption |
| Unknown | Chip shows "?" with a dusk border, no colour, key `speaker.unknown` |
| Unclaimed | Same as unknown until a claim maps the voice label |
| Overlap | Two chips shown with `cmd.overlap` as today |
| Voice off | No chips. Tap orders show the P label of the tapping player only if claimed, else none |

### Privacy rule

- The model only ever sees P1 to P4. Never send a typed or spoken name to any model. Canonical: `docs/architecture/ai-contracts.md` and the M9 note in `CLAUDE.md`.
- Names typed on VoiceClaim stay local. On screen the chip shows the label and shape. A local name may appear beside the chip on VoiceClaim only, never in narration payloads, never in logs.

### Accessibility

- `aria-label` reads "Player 1", "Player 2" and so on, from keys `speaker.p1` to `speaker.p4` (Proposed: tl "Manlalaro 1", en "Player 1").
- Pulse is replaced by a steady 2 px thicker border when reduced motion is on.
- Shape plus label plus colour. Colour-blind players read shape and label.
- Chip text stays at 16 px or larger.

### Acceptance checks

- [ ] A diarized caption shows the correct chip.
- [ ] Unknown speaker shows "?" and no colour.
- [ ] Each of P1 to P4 differs by shape in greyscale.
- [ ] No real name appears in any outgoing model request. Verify with the recorded fixtures and a log scan.
- [ ] Reduced motion shows no pulse.
- [ ] Chip text does not overflow a 440 px side column.
- [ ] Update `docs/design/hud-components.md` row from "Not built" when done.

## D. Synthesized sound

### Purpose

Add night mood and clear event feedback with no audio files and no licenses. All sounds are built at runtime with the WebAudio API from oscillators, noise and gain envelopes. This replaces the file-based plan in `docs/design/audio.md` for licensing. That file needs a sync (docs-sync task).

### Cues

Recipes are starting points. Tune by ear. All values are Proposed.

| Cue | Moment | Recipe | Length |
|---|---|---|---|
| Night ambience | Whole night, from turn 1 telegraph to Sunrise or Defeat | Low-passed noise bed at very low gain plus random cricket chirps (short 4 to 5 kHz sine bursts, 2 to 3 per burst, random gaps 0.8 to 3 s) | Loop |
| Spawn gong | Enemy spawn (SPAWN_TELEGRAPH) | Sine 110 Hz with two partials, fast attack, 1.2 s exponential decay | 1.2 s |
| End Turn bell | End Turn pressed or "Tapos na" | Sine 880 Hz plus 1320 Hz, soft attack, 0.8 s decay | 0.8 s |
| Hit | Damage to a unit or the kubo | Short noise burst through a band-pass, pitch drop sine 160 to 70 Hz | 0.2 s |
| Dodge | "Nakaiwas!" float | Quick upward sine sweep 600 to 900 Hz, low gain | 0.15 s |
| Sunrise | Phase SUNRISE | Rising chime: sine notes C5, E5, G5, C6 spaced 0.25 s, plus a short pitch-bend squawk at the end for a rooster-like feel | 2 s |
| Defeat | Phase DEFEAT | Sine 98 Hz fall to 65 Hz with slow decay | 2 s |

- Footsteps from `docs/design/audio.md` are cut for v1.
- Cues fire from the same rules events that drive animations. Narration timing does not matter.
- Never play more than 4 voices at once. Drop the oldest.

### Settings and storage

- Master gain default 0.25 (low). Ambience bed at 30% of master.
- Mute switch: key `desktop.sound` with value `on` or `off`. Default `on` at the low volume. A missing key counts as `on`.
- If `desktop.sound` is `off`, create no AudioContext cues and stop the bed.
- Settings screen is skipped. Controls are the switch in the Start footer and the switch in the Night pause overlay.
- Switch is a `.btn-quiet` with `role="switch"`, `aria-checked`, `PixelIcon` `check` or `cross`, label `sfx.on` or `sfx.off`.
- The AudioContext starts on the first user gesture (LanguagePick click or any key), as browsers require. Failure to create it is silent.
- Pause fades the bed out in 300 ms and Resume fades it back.

### Proposed copy (need cultural review)

| Key | tl | en |
|---|---|---|
| `sfx.on` | Tunog: naka-on | Sound: on |
| `sfx.off` | Tunog: naka-off | Sound: off |
| `gloss.open` | Mga Alamat | Folklore |

### Accessibility

- Sound is never the only signal. Every cue pairs with a visible one: phase banner for the gong, End Turn state for the bell, floating numbers and `kubo.hit` flash for hit, "Nakaiwas!" for dodge, scene change for Sunrise and Defeat.
- Default volume is low. Nothing is louder than the master default.
- Mute stays reachable from Start and the pause overlay. It is honored before any cue plays.
- No sudden loud starts. Every envelope ramps in at least 5 ms and out at least 20 ms.
- No speech output. The mic is not fed speech by the game.
- Speakers can leak into the mic. Risk: bell or gong picked up as a caption. Unverified. Verify in a live voice night with speakers on, and suggest push to talk or lower volume if captions appear.
- Reduced motion does not affect audio. The mute switch is the control.

### Acceptance checks

- [ ] Every cue plays once from its event and none plays twice.
- [ ] Setting `desktop.sound` to `off` silences all cues after reload.
- [ ] Default master level is audibly low on the demo laptop speakers.
- [ ] Ambience starts at turn 1 and stops at Sunrise, Defeat or Quit.
- [ ] Pause fades the bed. Resume restores it.
- [x] No audio file exists under `assets/sfx/`. No license notes needed. Verified 2026-11-03, the folder does not exist
- [ ] A night with sound on shows no phantom captions at normal speaker volume. If it does, record it as a risk.
- [ ] Blocked localStorage still lets the game start with sound on.
- [ ] Update `docs/design/audio.md` (done 2026-11-03) and the README credits section to say synthesized.
