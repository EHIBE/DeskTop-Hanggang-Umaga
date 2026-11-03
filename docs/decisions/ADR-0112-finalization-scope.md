---
title: ADR-0112 Finalization scope
purpose: Record what the finalization run builds, cuts and leaves as known gaps before the Nov 3 freeze
read_when: [choosing finalization work, questioning a cut, changing powers or progression]
canonical_for: [ADR-0112]
sources: [docs/FINALIZATION_PLAN.md#decisions-locked-on-2026-11-03, docs/game/powers.md, docs/product/scope-and-cuts.md]
status: active
last_verified: 2026-11-04
related: [docs/decisions/README.md, docs/FINALIZATION_PLAN.md, docs/design/onboarding-and-tutorial.md, docs/game/powers.md]
---

# ADR-0112: Finalization scope

Status: Accepted. Raised 2026-11-03. Accepted 2026-11-03 by EHIBE (D3, D4, D5, D19).

## Key facts

| Field | Value |
|---|---|
| Status | Accepted |
| Decided | 2026-11-03 |
| Owner | EHIBE |
| Build before freeze | Code-made sound cues, first-night tutorial hints, folklore glossary, speaker chip |
| Cut | Settings screen, campaign progression F16. Both reversed by ADR-0113 on 2026-11-04 |
| Power change | P08 Liwanag leaves the Charm and Scout lists while Kapre smoke is cut. Reversed by ADR-0113 on 2026-11-04 |
| Known gap | No Python dependency audit (pip-audit) |

## Context

The MVP is complete offline and the feature freeze is Nov 3 6:00 PM SGT. The remaining hours go to game feel that a judge sees in a 3-minute video. P08 only counters Kapre smoke, which is cut, so it was a dead pick on two classes. pip-audit would be a new dependency.

## Decision

- Build the four game feel features in `docs/FINALIZATION_PLAN.md` Phase 4, in that order, and cut them in the plan's cut order if time runs out.
- Do not build a Settings screen. The FIL and ENG toggle and the mute toggle live where they are used.
- Cut F16 campaign progression.
- Remove P08 from the Charm and Scout class lists in `backend/rules/units.py`. The `PowerId` enum keeps P08 and the existing clamp rule turns a P08 pick into the first power in the class list.
- Record the missing Python audit as a known gap. Do not add pip-audit.

## Consequences

- Every power a Charm or Scout can hold now has a target in the shipped enemy set
- Progression and Settings stay out of the demo and the docs mark them cut
- Python dependencies are not scanned for known vulnerabilities
- Follow-up: bring P08 back if Kapre smoke returns

## Alternatives considered

- Keep P08 as a no-op pick (rejected: a power with no effect reads as a bug to a judge)
- Add pip-audit (rejected: new dependency during the freeze week)

## Sources

- `docs/FINALIZATION_PLAN.md#decisions-locked-on-2026-11-03`
- `docs/game/powers.md`
