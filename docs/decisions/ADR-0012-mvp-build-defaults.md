---
title: ADR-0012 MVP build defaults
purpose: Record the defaults EHIBE approved at the MVP build clarification gate for rules, content, assets and runtime gaps the docs left open
read_when: [implementing damage, enemy movement, targeting, waves, voice claim, content filters, assets, backend startup, stage scaling]
canonical_for: [ADR-0012, damage with shields rule, duwende pre-steal hit, wall blocking rule, target tie-break, fail-closed token startup]
sources: [docs/MVP_BUILD_PROMPT.md#2-clarify-gate, docs/game/combat-math.md, docs/game/enemies.md, docs/game/waves-and-difficulty.md]
status: active
last_verified: 2026-10-29
related: [docs/decisions/README.md, docs/game/combat-math.md, docs/game/waves-and-difficulty.md, docs/game/powers.md]
---

# ADR-0012: MVP build defaults

Status: Accepted. Decided 2026-10-28 by EHIBE ("use defaults" at the MVP build clarification gate).

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-10-28 |
| Owner | EHIBE |

## Context

The PRD and derived docs leave several rules and runtime details open or contradictory. The MVP build prompt requires flagging every ambiguity before code. EHIBE approved the recommended default on each.

## Decision

| Topic | Decision |
|---|---|
| Damage with shields | Raw damage is `max(1, ATK + bonuses)`. Shield pools (P02, P06) absorb first, the rest reduces HP. A shield can block a hit fully. Event `dmg` is the HP actually lost |
| Duwende hit | A hit steals and deals 0 damage (Phase 12). Before Phase 12 it dealt 1 damage, the cut-list "fast weak hitter" |
| Walls | Enemies move in a straight line toward their target, no pathfinding. A non-flying enemy stops at first contact with a Wall unit footprint |
| Ties | Target and spawn ties break by nearest edge distance, then lowest SAM object ID |
| Unverified game defaults | Accepted as written: edges chosen North then clockwise and farthest apart, extra Aswang at the edge farthest from the kubo, spawn at the edge midpoint offset 5 cm per extra enemy, 1 player uses the 2-player table, P10 bonus ignores the ATK cap, P08 stays valid, tied Bayani players all shown, tracker-loss SAM delay 5 s |
| Voice claim before F11 | VOICE_CLAIM ships in the MVP with typed player names, tap-to-assign units, Skip and the 60 s timeout. Spoken claim was added in Phase 12 (see below) |
| Pixel font | Press Start 2P (SIL OFL 1.1) bundled in `assets/fonts/` with its license |
| Content filter lists | LDNOOBW English and Filipino lists (CC BY 4.0) and a PSGC province and city list in `backend/gm/data/`, with attribution |
| Placeholder, enemy and tile art | Generated with Muse Image in Phase 5.1 once the key is present |
| Audio | Deferred until after the MVP |
| Aswang spawn line | East, south and west variants added, marked Proposed until playtester review |
| Backend start | Refuses to start without `DESKTOP_TOKEN` (fail closed). Data root defaults to `%APPDATA%\DeskTop` when `DESKTOP_DATA_DIR` is unset |
| Stage | One fixed 1920x1080 stage scaled to fit the window with letterboxing. Sprites drawn nearest-neighbor at integer scales |
| Tailwind packages | Moved to devDependencies with versions unchanged |
| ffmpeg | Manual: EHIBE installs it before Phase 13 |
| Class caps (added M4) | A summon that would be a third Charm or a third Wall becomes a Fighter (Fighter template, power falls back to P03). The first summon is always the kubo and ignores caps |
| Game ids (added M4) | `u_kubo` for SAM slot 1, `u_<slot>` for slots 2 to 12. Stable for the night even when a unit is renamed |
| Re-rolls (added M4) | One per unit, recorded in `night.flags_json` under `rerolls`, so a backend restart cannot reset it |
| Offline summon (added M4) | Without a key, with Demo Safe on, or when Spark fails: the player taps the new object, a 6 x 6 cm box around the tap becomes the mask (SAM point prompt when SAM is up), and the card is the class default (Fighter, or the kubo first) |
| Rules details (added M7) | A power just used keeps its full cooldown, unused powers tick down 1 at turn end. A power that fails at resolution emits a dodge and starts no cooldown. A unit with range none uses 5 cm melee reach for range powers. P09 picks the enemy nearest the first target, spawn order on ties. P11 and P12 emit power then attack. Area powers accept no target. Aswang isolation counts the kubo as an ally. Isolation and aura checks have no +1 cm tolerance. A board with only the kubo continues. A fully shielded hit emits attack with dmg 0. A dead manananggal lower half removes the upper silently. A dead upper reforms on the second following turn beside the lower. Enemy ids are `e_<type>_<n>`, lower half before upper. Stacked difficulty and player extras both apply. New enemies move and telegraph on the turn they spawn. Movement steps 0.25 cm then bisects to the exact boundary |
| Night flow (added M7) | Voice claim allows 4 players. Next Night starts a fresh summon (returning objects are F16, a Could). Re-anchor failure at End Turn returns to PLAYER_PHASE. The 60 s voice claim timeout finishes claims automatically (added M10) |
| Narration (added M9) | The first narration goes out when claims finish, with phase night_start and turn 1 spawns. Each resolved turn sends one narration for resolution plus the next telegraph. A blocked End Turn sends none. GM calls use `CallKind.SPARK` (20 s) under `NARRATION_TIMEOUT_S` 20 s, then the line bank. Each call sends the full GM input with `store` false and no `previous_response_id` chain, so nothing is kept at Meta (privacy audit). Players go out as P1 to P4. The recap schema waits for F16. Line bank picks are deterministic by night, turn and moment |
| Safety (added M10) | Begin Night on a saved night resumes it, skipping voice claim, and owners come back from the store. The camera check runs on the End Turn still frame only, not every frame, so hands mid-turn never trigger it. Delete campaign is allowed from START only and keeps `api_usage` for the cost audit. Sprites shared with another campaign stay |
| Voice (added M11) | One DIARIZATION session on the default microphone starts when claims finish or on restore, stops while paused, at sunrise, defeat, quit and in Demo Safe, and restarts on resume or when Demo Safe turns off. Keywords hold creature words, order verbs and unit names, never player names. A 1008 close retries once without languageBias and keywords. Three failed connects set status down with `net.down` and tap controls, with no automatic switch to the PUSH_TO_TALK mode. Push-to-talk gates audio locally and sends silence frames while the key is up. Orders apply only in PLAYER_PHASE. Cancel fires only when a cancel word opens the utterance and removes that speaker's last voice chip, or any voice chip when the speaker is unknown. A lone tapos is a connector, so End Turn needs tapos na, done, end, next or a bare tapos. Callbacks from an old session after a retry are ignored |
| Physical enemies (added Phase 12) | Any connected tikbalang hit pushes the target 8 cm away, even when shields stop the damage. The kubo and downed units are never pushed. A spot off the play area throws the unit instead: it stays where it is and is out for one full turn. A duwende hit steals instead of damaging, the carrier flees 12 cm per turn to the nearest edge (ties north, east, south, west) and escapes at the next turn start within 2 cm of it. Killing the carrier returns the unit at its spot. An escaped unit is lost for the night, counts as not alive and can end the night at once. Returning units skip one move check so the object can go back anywhere. Out, stolen and lost units cannot act, be targeted, block or buff. One physical effect per unit, a steal beats a push. On timeout or the Done tap the pushed unit takes its tracked spot. A crash during PHYSICAL_EFFECTS replays the turn from the last autosave |
| Voice claim (added Phase 12) | Voice runs on the claim screen. "ako si" and "hawak ko" forms come from `voice/claim.py`. A spoken claim can take a unit from another player, the same as tap. Mid-night only known player names re-map a label |
| Recording and evals (added Phase 13) | Consent is asked per claimed player on the claim screen and recording starts only when all agree. No answer counts as no. Recording runs from claims to sunrise, defeat, quit or close, through pauses, at 25 FPS with paced duplicate or skipped frames, a queue of 8 that drops and counts overflow, and ffmpeg from PATH or DESKTOP_FFMPEG. A missing ffmpeg shows `rec.unavailable` and the night goes on. The freeze tag in Build Guide 13.4 is a git tag and push, which the build rules forbid for agents, so EHIBE runs it. The eval runner never scores without real inputs |
| Replay (added Phase 14) | A reel can be made at sunrise or defeat when the night has a consented recording. Highlights: last turn, then kubo hits by damage, kills, split, steal, push, 8 s windows starting 3 s before the event, at most 6, no overlaps. Without the key, in Demo Safe or when SAM video fails, sprites pin to the saved anchor boxes. The reel is 1080p 30 FPS, 60 s max, with a 3 s dawn title card and 0.3 s crossfades. The renderer reveals the file through the `desktop:show-reel` IPC, which accepts only `reel_<name>.mp4`, checks the sender, and refuses links and paths outside the recordings folders |
| Begin Night block (added M4) | `summon.kubo_first` when there is no kubo, `summon.need_units` for every other invalid roster |

## Consequences

- Rules code and tests follow this table. Game docs point here for these rules
- Proposed copy lines still need 2 Filipino playtesters
- Asset steps wait for the key (Manual: EHIBE)

## Alternatives considered

- Literal formula `max(1, ATK + bonuses - shield)` (rejected: conflicts with "absorbs the next 2 damage")
- Pathfinding around walls (rejected: KISS, not in the PRD)
- A `"dev"` token default (rejected: fails open)

## Sources

- `docs/MVP_BUILD_PROMPT.md#2-clarify-gate`
- `docs/game/combat-math.md`
- `docs/game/waves-and-difficulty.md`
