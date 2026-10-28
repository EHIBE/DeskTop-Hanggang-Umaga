---
title: README outline
purpose: Structure and sources for the root README written in Phase 15
read_when: [writing the root README.md]
canonical_for: [README outline, license default]
sources: [docs/DeskTop_PRD.md#readme-outline, docs/DeskTop_Build_Guide.md#152-readme]
status: active
last_verified: 2026-10-28
related: [docs/delivery/submission-checklist.md, docs/product/product-brief.md]
---

# README outline

The root README does not exist yet and is written in Phase 15. Each section below names the doc to pull from, so the README summarizes rather than duplicates.

## Key facts

| Fact | Value |
|---|---|
| File | `README.md` at repo root (Phase 15) |
| License default | MIT code, CC BY-NC 4.0 assets made for DeskTop, third-party assets keep their own (Q3, decide by Nov 3) |

## Sections

| # | Section | Pull from |
|---|---|---|
| 1 | Title, tagline, 20 s GIF | `product/product-brief.md`, demo footage |
| 2 | What it is (3 lines) | `product/product-brief.md` |
| 3 | How it uses Meta models (table) | `architecture/meta-api-integration.md` |
| 4 | Architecture diagram | `architecture/overview.md` |
| 5 | Requirements (Windows, webcam, A4, API key) | `engineering/setup-windows.md` |
| 6 | Setup in 5 commands | `engineering/setup-windows.md` |
| 7 | How to play (setup, summon, night, sunrise) | `game/core-loop.md` |
| 8 | Eval results (E1 to E7) | `docs/eval.md` (real numbers only) |
| 9 | Cost per night | `architecture/cost-and-budget.md` plus measured api_usage |
| 10 | Privacy (what is sent, what stays local) | `engineering/security-and-privacy.md` |
| 11 | Known limits | `product/scope-and-cuts.md`, `delivery/risk-register.md` |
| 12 | Credits (assets, fonts, sounds with licenses), folklore glossary | `design/audio.md`, `design/art-direction.md`, `design/cultural-care.md` |
| 13 | License | This file |

## Rules

- No unsourced numbers. Eval and cost numbers from real runs.
- No secrets, no private paths beyond the repo.
- Keep app/README.md (scaffold) or replace it with a short pointer to the root README.
