---
title: Docs index
purpose: Map of every project document and the read order for each kind of task
read_when: [start of any task, looking for where a fact lives]
canonical_for: [doc map, doc conventions, read order]
sources: [CLAUDE.md, docs/DeskTop_PRD.md, docs/DeskTop_Build_Guide.md]
status: active
last_verified: 2026-11-04
related: [CLAUDE.md, llms.txt, README.md, docs/glossary.md, docs/prompts/FEATURE_PROMPT.md, docs/delivery/build-log.md]
---

# Docs index

This file maps every document in `docs/` and says which ones to read for each kind of task. Each fact has one canonical home, listed in the `canonical_for` front matter of that file.

## Key facts

| Fact | Value |
|---|---|
| What to build | `DeskTop_PRD.md` v1.1 (canonical source, kept unchanged) |
| How and when to build | `DeskTop_Build_Guide.md` (canonical for schedule, phases, cut list) |
| Working prompt | `prompts/FEATURE_PROMPT.md`. Docs work: `prompts/DOCS_FEATURE_PROMPT.md`. Finalization roadmap: `FINALIZATION_PLAN.md` |
| Entry points | Humans: `../README.md`, then `how-to-run.md`. AI: `../CLAUDE.md`, then this file, then `../llms.txt` |
| History | `delivery/build-log.md`. CLAUDE.md State holds current state only |
| Precedence | Code beats docs on what exists. PRD beats derived docs on what to build. Build Guide beats PRD on schedule and cuts |
| Conflicts | Recorded as ADRs in `decisions/` |

## Source documents

| File | Role |
|---|---|
| `DeskTop_PRD.md` | Full product requirements, 22 sections. Historical source of truth |
| `DeskTop_Build_Guide.md` | Phase 0 to 15 build plan, schedule, cut order |
| `prompts/SUPER_PROMPT.md` | EHIBE's original generator prompt, verbatim. It produced the feature prompt and the finalization plan |
| `prompts/SUPER_PROMPT_DOCS.md` | EHIBE's second generator prompt, verbatim. It produced the docs feature prompt |
| `prompts/DOCS_FEATURE_PROMPT.md` | Prompt for docs work: audience rules, Markdown rules, drift list. Run it for any documentation update |
| `prompts/FEATURE_PROMPT.md` | Master prompt every feature run follows. Older prompts in `prompts/archive/` |
| `FINALIZATION_PLAN.md` | Ordered Nov 3 to Nov 5 roadmap to a submitted, production-ready build |
| `how-to-run.md` | Friendly guide to install, launch and play the game. Start here if you just want to play |
| `eval.md` | Eval results E1 to E7 (real runs only) |
| `playtests.md` | Playtest logs (real sessions only) |
| `rules-notes.md` | Official Rules answers, event page facts and smoke-test findings |
| `images/` | README and guide screenshots, captured from the running app over CDP |

## Derived documents

| Folder | Files | Covers |
|---|---|---|
| `product/` | product-brief, goals-and-metrics, personas-and-jobs, requirements-index, scope-and-cuts, open-questions, user-journey | Why, for whom, what, status |
| `market/` | market-and-audience, competitive-landscape, positioning-and-messaging, launch-and-community, judging-strategy | Market, rivals, message, judges |
| `game/` | core-loop, state-machine, units-and-classes, powers, enemies, waves-and-difficulty, combat-math, win-lose-score, campaign-progression, balance-and-tuning | Rules |
| `design/` | DESIGN, screens, hud-components, copy-deck, art-direction, audio, accessibility, cultural-care, onboarding-and-tutorial | Look, feel, words |
| `architecture/` | overview, backend-modules, frontend-modules, websocket-protocol, data-model, meta-api-integration, ai-contracts, sprite-pipeline, tracking-and-reanchor, voice-pipeline, reliability-and-fallbacks, cost-and-budget | System and contracts |
| `engineering/` | setup-windows, coding-standards, testing-strategy, security-and-privacy, environment-and-config, git-and-commits, definition-of-done, troubleshooting | How to work |
| `delivery/` | schedule, risk-register, demo-runbook, video-script, submission-checklist, readme-outline, judging-scorecard, submission-text, release-and-packaging, live-api-runbook, handoff-ui-redesign, build-log | Shipping and history |
| `decisions/` | README, template, ADR-0001 to ADR-0012, ADR-0101 to ADR-0113 | Why things are the way they are |
| root | `glossary.md` | Terms and ID prefixes |
| repo root | `README.md`, `llms.txt`, `CLAUDE.md`, `LICENSE` | Human overview, AI link list, agent memory, license |

## Read order by task

| Task | Read, in order |
|---|---|
| Any task | `CLAUDE.md`, this file |
| Rules engine work | `game/combat-math.md`, `game/units-and-classes.md`, `game/powers.md`, `game/enemies.md`, `game/waves-and-difficulty.md`, `game/state-machine.md`, `engineering/testing-strategy.md` |
| Vision work | `architecture/meta-api-integration.md`, `architecture/tracking-and-reanchor.md`, `architecture/sprite-pipeline.md`, `architecture/reliability-and-fallbacks.md`, `architecture/cost-and-budget.md` |
| Voice work | `architecture/voice-pipeline.md`, `design/copy-deck.md`, `architecture/reliability-and-fallbacks.md` |
| GM and prompts | `architecture/ai-contracts.md`, `design/cultural-care.md`, `design/copy-deck.md` |
| UI work | `design/DESIGN.md`, `design/screens.md`, `design/hud-components.md`, `design/copy-deck.md`, `design/accessibility.md`, `architecture/websocket-protocol.md` |
| Electron or security | `engineering/security-and-privacy.md`, `architecture/frontend-modules.md`, `architecture/websocket-protocol.md` |
| Data | `architecture/data-model.md` |
| Finalization | `FINALIZATION_PLAN.md`, `delivery/judging-scorecard.md`, `delivery/live-api-runbook.md`, `delivery/release-and-packaging.md` |
| Demo prep | `delivery/demo-runbook.md`, `delivery/video-script.md`, `delivery/submission-checklist.md`, `market/judging-strategy.md` |
| Docs work | this file, `prompts/DOCS_FEATURE_PROMPT.md` section 4.7, `decisions/README.md`, `../llms.txt` |
| Project history | `delivery/build-log.md`, `decisions/README.md` |

## Conventions for adding docs

- Front matter keys: title, purpose, read_when, canonical_for, sources, status, last_verified, related.
- First body line is a two-sentence summary. Then a Key facts table.
- One topic per file. Under 300 lines.
- Keep each fact canonical in one file. Elsewhere write "Summary. Canonical: path#anchor".
- Use existing IDs: FR, NFR, F, R, E, P, JS, PG, A, Q, copy keys, state names. New decisions get the next ADR number.
- Mark unverified items "Unverified" with the step that verifies them.
- Prose has no semicolons and no em dashes.
- After any change, run the `desktop-docs-sync` skill.
