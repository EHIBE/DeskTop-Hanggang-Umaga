---
name: desktop-add-copy-key
description: "Add or change any player-facing text in DeskTop: UI strings, prompts, banners, GM line bank lines, unit card text, captions or social hook lines, in Taglish with an English caption and cultural-care review. Use this whenever a screen, HUD element, error path or narration needs words, even for a single short message like 'show a warning when the camera moves'."
---

# Add a copy key

DeskTop speaks Taglish to Filipino players and English to everyone else, and it handles folklore that real communities live with. One stray English-only error or a careless line about a creature undoes that. All text lives under keys so it can be reviewed in one place.

## Steps

1. Read `docs/design/copy-deck.md` and `docs/design/cultural-care.md`. Reuse an existing key if one fits.
2. Name the key `area.purpose` (for example `cam.moved`, `cmd.overlap`).
3. Write the Taglish line the way young Filipinos talk with friends, max 2 short sentences. Write a plain English line with the same meaning.
4. Use only the existing placeholders ([unit], [player], [HP], [n], [feature], [object], [target], [action], [name]).
5. Check: no gore, slurs, politics, mocked religion, or a real place tied to a monster.
6. Add the key to `app/src/renderer/src/lib/copy.ts` (UI) or `assets/lines.json` (narration) once those exist, and to the table in `copy-deck.md`. Mark new keys Proposed until 2 Filipino playtesters review them.
7. Render it through React or canvas text, never as raw HTML.

## Done when

- Key exists in code and the copy deck, both languages present, review row added to `docs/playtests.md`.

## Delegate

`desktop-cultural-reviewer` for a read-only check before recording.

## Always

- Follow `docs/prompts/FEATURE_PROMPT.md` sections 4, 5 and 9. Hard constraints win over this skill.
- Any agent you spawn runs on Sonnet 5.5 at medium effort (pass model sonnet).
- No code comments, no debug code, no new dependencies without EHIBE's approval.
- Doc prose has no semicolons and no em dashes.
- Finish with the `desktop-docs-sync` skill, then commit per `docs/engineering/git-and-commits.md` (EHIBE sole author, no trailers).
