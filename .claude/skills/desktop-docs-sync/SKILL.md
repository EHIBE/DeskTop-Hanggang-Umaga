---
name: desktop-docs-sync
description: "Bring DeskTop's docs, CLAUDE.md state, pending queue, bugs and requirement statuses in line with what just changed in code or decisions. Use this at the end of every feature, fix or decision, whenever a number, threshold, file path, message, schema or scope changes, or when the user asks to update docs, even if they only say 'wrap this up'."
---

# Docs sync

Agents in later sessions trust these docs instead of re-reading the code. A stale doc sends them the wrong way, so every change ends by updating the one canonical place for each fact it touched.

## Steps

1. List what changed: files, functions, numbers, messages, schemas, decisions, scope.
2. For each fact, find its canonical file through the `canonical_for` front matter or `docs/README.md`. Edit there. Elsewhere, keep only "Summary. Canonical: path" pointers.
3. Update statuses in `docs/product/requirements-index.md` (Planned, Built, Tested, Cut, Could).
4. Update `CLAUDE.md`: State table, Pending queue (remove done items, add new ones), Bugs and contradictions, Decisions.
5. New decision or resolved contradiction: add or update an ADR in `docs/decisions/` and its index row.
6. Record real eval results in `docs/eval.md` and playtests in `docs/playtests.md`. Never invent results.
7. Set `last_verified` to today on every doc you checked.
8. Check prose for semicolons and em dashes, and check links resolve.

## Done when

- No doc contradicts the code. CLAUDE.md reflects today's state.

## Delegate

`desktop-docs-keeper` for a read-only drift audit after large changes.

## Always

- Follow `docs/prompts/FEATURE_PROMPT.md` sections 4, 5 and 9. Hard constraints win over this skill.
- Any agent you spawn runs on Sonnet 5.5 at medium effort (pass model sonnet).
- No code comments, no debug code, no new dependencies without EHIBE's approval.
- Doc prose has no semicolons and no em dashes.
- Finish with the `desktop-docs-sync` skill, then commit per `docs/engineering/git-and-commits.md` (EHIBE sole author, no trailers).
