---
title: Enemy roster
purpose: Stats, AI target rules, specials and physical desk interactions for every enemy
read_when: [implementing backend/rules/enemies.py, enemy sprites, physical effects]
canonical_for: [enemy stats, enemy AI rules, physical interactions, enemy cuts]
sources: [docs/DeskTop_PRD.md#enemy-roster-normal-difficulty, docs/DeskTop_Build_Guide.md#phase-8-core-enemies-and-waves-oct-31-to-nov-1-2-h-f07, docs/DeskTop_Build_Guide.md#phase-12-voice-claim-and-physical-enemies-nov-2-4-h-f11--f08]
status: active
last_verified: 2026-11-04
related: [docs/game/waves-and-difficulty.md, docs/game/powers.md, docs/design/cultural-care.md]
---

# Enemy roster

Five folklore creatures, all virtual sprites on screen. Only player units are real objects.

## Key facts

| Fact | Value |
|---|---|
| Enemies | Aswang, Tikbalang, Kapre, Manananggal (upper and lower), Duwende |
| Footprint | Circle of radius 2 cm |
| Must (F07) | Aswang, Manananggal, telegraph |
| Should (F08) | Tikbalang push, Duwende steal, Kapre smoke |
| Movement | Up to move distance toward target, stops at attack range. Walls block. Repel auras block ending inside |

## Stats (Normal difficulty)

| Enemy | HP | ATK | Move | Range | AI target rule | Special |
|---|---|---|---|---|---|---|
| Aswang | 3 | 2 | 15 cm | 5 cm | Isolated unit (no ally within 10 cm), else lowest HP unit, else kubo | Fast |
| Tikbalang | 5 | 1 | 10 cm | 5 cm | Nearest unit | Hit pushes target 8 cm straight away |
| Kapre | 8 | 3 | 5 cm | 9 cm | Kubo | Smoke on its 2nd and 4th turn alive (built 2026-11-04) |
| Manananggal (upper) | 4 | 2 | 20 cm, flies over walls | 5 cm | Kubo, else nearest | Re-forms after 2 turns if upper dies and lower lives |
| Manananggal (lower) | 3 | 0 | 0 | none | none | Stays at spawn. Killing it ends both halves at end of turn |
| Duwende | 2 | 0 | 12 cm | 5 cm | Charm, else lowest HP non-kubo unit | Hit steals the unit, then flees 12 cm per turn to the nearest edge |

Difficulty modifiers: `waves-and-difficulty.md`.

## Physical desk interactions

| Enemy | Interaction | Steps | Copy keys |
|---|---|---|---|
| Tikbalang | Push | Compute target spot 8 cm straight away. Draw a ghost outline. Wait until the tracker shows the object within 2 cm of it, or 20 s then accept the current spot. Target off the desk: unit out for 1 turn, no move needed | `tik.push` |
| Duwende | Steal | Unit stolen. Player removes the object. Duwende flees 12 cm per turn. Killed: return mark shown, player puts the object back. Escapes: unit lost for the night. Ignored for 20 s: unit counts as removed even if the object stays | `duw.steal`, `duw.back`, `duw.escape` |
| Kapre | Smoke | A 10 cm cloud centred on the Kapre on its 2nd and 4th turn alive, lasting until the end of that round. A unit whose hull touches a cloud cannot hit an enemy standing outside every cloud. P08 Liwanag clears clouds within 12 cm before attacks. Events `smoke` and `smoke_cleared`. Arrow hiding is a renderer matter and is in progress | `kapre.smoke`, line bank `kapre_smoke_telegraph`, `kapre_smoke_hit` |
| Manananggal | Split | Upper and lower spawn together. Players must find and kill the lower half | `mana.split` |

## Current cuts

Kapre smoke is no longer cut (ADR-0113).

| Cut | Replacement | Source |
|---|---|---|
| Duwende steal (cut order 1, only if a day slips) | Fast weak hitter | Build Guide cut order |

## "Tabi tabi po"

Saying it during Set the table sets a night flag that skips the turn 2 duwende. Line bank: "Narinig ka ng mga duwende. Mukhang mabait sila ngayong gabi."

## Art

Pre-generated during development with Muse Image, 2-frame bob animation, poof-of-smoke defeat. No gore. Files in `assets/sprites/enemies/`.
