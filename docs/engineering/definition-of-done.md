---
title: Definition of done
purpose: Checklist every feature must pass before it is reported and committed
read_when: [finishing any feature]
canonical_for: [definition of done]
sources: [docs/prompts/FEATURE_PROMPT.md#6-verify, docs/prompts/FEATURE_PROMPT.md#7-document, docs/DeskTop_Build_Guide.md#how-to-use-this-guide]
status: active
last_verified: 2026-10-28
related: [docs/engineering/testing-strategy.md, docs/engineering/git-and-commits.md, docs/product/requirements-index.md]
---

# Definition of done

A feature is done when it works end to end, passes every check, and the docs say so. The Build Guide phase "Done when" line is the minimum bar.

## Key facts

| Gate | Check |
|---|---|
| Behavior | PRD Given/When/Then passes for every FR touched |
| Tests | New tests for happy path, edge, invalid, unauthorized, abuse, failure. All green |
| Static | Typecheck, lint, format clean. Python analyzer when configured |
| Security | Section 5 of the feature prompt checked |
| Docs | Owning doc, requirements-index status, CLAUDE.md updated |
| Commit | Format and authorship rules followed |

## Checklist

- [ ] Acceptance criteria restated and all met
- [ ] Build Guide phase "Done when" met
- [ ] No stubs, TODOs, placeholders, debug code or comments
- [ ] Every integration point wired (routes, WS types, spawn env, preload, router, state machine, copy keys, Demo Safe Mode, api_usage)
- [ ] Works in Demo Safe Mode or degrades per `reliability-and-fallbacks.md`
- [ ] Tests added and passing offline
- [ ] `npm --prefix app run typecheck`, `lint`, `format` clean
- [ ] `npm --prefix app audit` checked for touched packages
- [ ] Confirmed in the running app with the `run` skill (UI or integration changes)
- [ ] Security checklist for touched areas
- [ ] Copy reviewed for cultural care
- [ ] Docs updated with the `desktop-docs-sync` skill
- [ ] Commit made per `git-and-commits.md`
- [ ] Report: per-block summary, files, skills and agents used, real verification output
