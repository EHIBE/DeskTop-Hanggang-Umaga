---
title: Personas and job stories
purpose: Who DeskTop is for and the jobs they hire it to do
read_when: [designing a flow, writing copy, framing impact]
canonical_for: [personas, JS-01 to JS-14]
sources: [docs/DeskTop_PRD.md#5-users-personas-and-job-stories, docs/DeskTop_PRD.md#3-problem-alignment]
status: active
last_verified: 2026-11-04
related: [docs/market/market-and-audience.md, docs/product/requirements-index.md]
---

# Personas and job stories

Four fictional personas and fourteen job stories drive every requirement. Customer insights are mostly assumptions from builder experience until playtests.

## Key facts

| Fact | Value |
|---|---|
| Primary persona | Migs, the barkada host |
| Personas | 4 (all fictional) |
| Job stories | JS-01 to JS-14 |
| Evidence level | Mostly assumption, see insights table |

## Personas

| Persona | Profile | Needs | Frustration today |
|---|---|---|---|
| Migs, the barkada host | 21, college student, hosts friends after class, owns a laptop, no console | Something the whole group plays together in 15 minutes | Everyone ends up on their own phone |
| Ma'am Joy, the org or class facilitator | Org adviser or teacher who runs icebreakers for 20 to 40 students | A short, safe, local activity that gets groups talking | Icebreakers feel generic and English-only |
| Bea, the casual first-timer | Never plays tabletop games, joins because friends are playing | Understand the game in one minute and not feel slow | Rulebooks, setup, feeling lost |
| The judge | Meta or partner engineer who watches the video and may try the build | See in one minute that it works, uses the models well and matters | Demos that fake the hard part or break live |

## Problem statement

| Part | Statement |
|---|---|
| Who | Groups of friends, students and families in the Philippines who are together but play on separate screens |
| What | Tabletop games need bought pieces, setup and usually English rules. Video games need consoles or one screen per person |
| Evidence | Builder's firsthand experience (assumption until playtests). No survey data. No statistics claimed |
| Why it matters | Shared in-person play builds friendship and is cheaper than buying games. Local folklore and Taglish are rarely the core of a game |
| Why now | Models can now see objects, segment them, redraw them in a game style and understand code-switched Tagalog |

## Customer insights

| Insight | Type |
|---|---|
| Friends gather at tables but each ends up on a phone | Assumption |
| Filipino players respond strongly to aswang, tikbalang and kapre stories | Assumption |
| Taglish is the natural spoken mode for many young Filipinos in casual play | Assumption |
| Laptop and webcam are more common in student groups than a console | Assumption |
| Muse Voice Transcribe supports Tagalog with code-switching | Evidence: dev.meta.ai speech to text docs |
| SAM 3.1 keeps stable identity in video and supports up to 16 prompted objects | Evidence: dev.meta.ai SAM docs |

Market evidence gathered 2026-10-28: `docs/market/market-and-audience.md`.

## Job stories

| ID | Job story | Main FRs |
|---|---|---|
| JS-01 | When my friends come over with nothing planned, I want to start a game with what is already on the table, so I can skip buying or setting up a board game | FR-01 to FR-03 |
| JS-02 | When I put an object on the desk, I want it to become a character that looks like it, so I feel the game is made from my stuff | FR-06 to FR-16, FR-54 |
| JS-03 | When I plan with friends, I want to talk normally in Taglish, so I can play without learning English commands | FR-17, FR-18, FR-20, FR-21, FR-23, FR-38, FR-55 |
| JS-04 | When I give an order, I want to see it on screen before it happens, so I can cancel a mishearing | FR-19, FR-22 |
| JS-05 | When I move a piece by hand, I want to see right away whether the move is legal | FR-26, FR-28, FR-30, FR-32, FR-33 |
| JS-06 | When an enemy is about to attack, I want to see who it will hit | FR-34 to FR-36, FR-40 |
| JS-07 | When my hand covers a piece, I want the game to wait instead of losing it | FR-27, FR-29 |
| JS-08 | When we survive, I want a replay of our real hands and the pixel battle to post | FR-44 to FR-48 |
| JS-09 | When we play again tomorrow, I want the game to remember our kubo and units | FR-13, FR-42, FR-43, FR-53, FR-56 |
| JS-10 | When the internet is slow, I want the game to keep going | FR-04, FR-24, FR-39, FR-41, FR-50, FR-52 |
| JS-11 | When I run an activity for a group, I want a 15 minute session with clear win or lose | FR-05, FR-31, FR-37 |
| JS-12 | When I am new, I want the first turn to teach me with one easy enemy | FR-15 |
| JS-13 | When I am judging, I want to see which model does what | FR-50, FR-51 |
| JS-14 | When I cannot or do not want to speak, I want a tap button for every action | FR-25, FR-49 |
