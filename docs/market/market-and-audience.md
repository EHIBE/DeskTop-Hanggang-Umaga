---
title: "Market and Audience for DeskTop: Hanggang Umaga"
purpose: Evidence-backed view of the Philippine gaming, tabletop, device, connectivity, language and diaspora context that DeskTop launches into.
read_when:
  - writing impact framing or the Build for Your World pitch
  - deciding launch audiences and channels
  - checking whether a market claim has a source
canonical_for:
  - Philippine market and audience facts with sources
  - device and connectivity constraints for the target audience
  - labeled assumptions about audience behavior
sources:
  - https://allcorrectgames.com/insights/the-filipino-game-market/
  - https://www.kenresearch.com/industry-reports/philippines-gaming-and-mobile-entertainment-market
  - https://www.back2gaming.com/games/philippine-gaming-market-report-august-2026/
  - https://datareportal.com/reports/digital-2026-philippines
  - https://pids.gov.ph/details/resource/infographics-infobits/infobits-on-computer-ownership-in-ph
  - https://newsinfo.inquirer.net/1402235/sws-58-of-pinoy-students-used-devices-for-distance-learning/amp
  - https://pro.edgex.exchange/en-US/news/article/philippines-climbs-ookla-speed-rankings-august-2026
  - https://gad.cfo.gov.ph/wp-content/uploads/2025/01/2014-CFO-Compendium-of-Statistics-on-International-Migration.pdf
  - https://manilatimes.net/2024/09/16/news/national/number-of-ofws-surges-to-216m-in-2023/1971631
  - https://www.imarcgroup.com/philippines-board-games-market
  - https://abs-cbn.com/lifestyle/2025/5/30/qc-aspires-to-become-board-game-capital-of-southeast-asia-1423
  - https://www.fixgamingchannel.com/mimic-manila-2026-ttrpg-convention-makati/
  - https://globalvoices.org/2021/08/11/netflix-animation-trese-brings-filipino-supernatural-beings-into-the-screens/
  - https://usurj.journals.usask.ca/article/view/763
  - https://www.outsourceaccelerator.com/glossary/game-developers-association-philippines/
  - https://gmanetwork.com/news/scitech/technology/809092/pinoy-made-game-good-knight-is-on-sale-available-on-steam-early-access/story
status: active
last_verified: 2026-11-04
related:
  - docs/product/personas-and-jobs.md
  - docs/market/positioning-and-messaging.md
  - docs/market/judging-strategy.md
  - docs/DeskTop_PRD.md
---

The Philippines is a large, young, mobile-first gaming market with a growing tabletop scene, strong interest in its own folklore, and a big overseas diaspora, but laptop ownership is the weak point for DeskTop's hardware needs. This file lists what is sourced, what is assumed, and how each assumption would be validated by the playtests in PRD section 18.

## Key facts

| Fact | Value | Source |
|---|---|---|
| Internet users, Oct 2025 | 98.0 million, 83.8 percent of population | [S4] |
| Social media user identities, Oct 2025 | 95.8 million | [S4] |
| Smartphone ownership among internet users, 2025 | 98.6 percent | [S4] |
| Laptop or desktop use among internet users, 2025 | 62.7 percent | [S4] |
| Households owning a computer, 2018 | 20.66 percent | [S5] |
| Students 5 to 20 using devices for distance learning, 2020 | 58 percent, with 19 percent of urban students using a laptop or desktop | [S6] |
| Median fixed broadband download, Aug 2026 | 114.34 Mbps (global median 129.68) | [S7] |
| Median mobile download, Aug 2026 | 66.33 Mbps (global median 109.05) | [S7] |
| Market structure | Largely mobile, many gamers also own a PC, console share markedly lower | [S1] |
| Gaming and mobile entertainment market, 2025 estimate | USD 1,500 million, forecast USD 3,696 million by 2032 | [S2] |
| Board game market, 2025 estimate | USD 91.9 million, forecast USD 223.5 million by 2034 | [S10] |
| Overseas Filipinos stock estimate, Dec 2013 | About 10.2 million | [S8] |
| Overseas Filipino workers, Apr to Sep 2023 | 2.16 million (PSA) | [S9] |
| Trese on Netflix, 2021 | Reached No. 1 in the Philippines and stayed 10 straight days | [S14] |
| Taglish in TV ads, one study | 51 percent of words code-switched to English | [S15] |
| Game studios per GDAP, around 2014 | About 60 studios, about 3,500 staff | [S16] |

Note on [S2]: a market research vendor estimate. Treat as indicative only. Methodology was not reviewed.

## Philippine gaming market

- Market is largely mobile. Many gamers also own a PC. Console share is markedly lower [S1].
- Data year for [S1] is not stated on the page. Treat as undated.
- Google Play top free list in Aug 2026 led by Mobile Legends and Roblox. Paid list led by Minecraft and Stardew Valley, plus Filipino-made Rayadillo Mobile PH [S3].
- Console prices are rising. PS5 Standard listed at USD 649.99 in Aug 2026 [S3]. Hardware inflation pushes players to low-hardware titles [S3].
- Implication: DeskTop targets PC, the second platform in this market, and avoids the console cost barrier.
- Not found: a primary-source count of Filipino PC gamers. Do not claim one.

## Devices and connectivity

- Smartphones are near universal among internet users (98.6 percent) [S4].
- Laptop or desktop use among internet users is 62.7 percent [S4]. This is use, not ownership, and covers all adults.
- Household computer ownership was only 20.66 percent in 2018 [S5]. This is old and probably higher now.
- During 2020 distance learning, 19 percent of urban students used a laptop or desktop [S6]. This is a pandemic-era snapshot.
- Assumption: a barkada of 3 to 4 college students usually includes at least one working Windows laptop. Validate by asking every playtest group what device they have.
- Assumption: a built-in or cheap USB webcam can see an A4-sized desk area from a stand. Validate in PRD section 18 hardware tests.
- Connectivity is adequate for DeskTop's small uploads. Fixed median 114.34 Mbps, mobile 66.33 Mbps in Aug 2026 [S7].
- Provincial and campus Wi-Fi may be well below the national median. Assumption, validate by running Demo Safe Mode and a throttled test.

## Board game and tabletop culture

- Board game cafes exist in Metro Manila and beyond, such as Ludo (Quezon City, Makati) and Vault in Cebu [S11].
- Quezon City hosted the All aBOARD 2025 Expo in May 2025 with more than 300 games and aims to be the board game capital of Southeast Asia [S10] [S12].
- Mimic Manila 2026, a TTRPG convention, ran three days in Makati and ended Oct 4, 2026 [S13].
- Asian Board Games Festival Philippines was scheduled for May 2 to 3, 2026 at Bayanihan Center [S11].
- Local designers use folklore as a hook. Examples are Lagim, Engkanto and Tadhana (see competitive-landscape.md).
- Gap: the hobby scene is concentrated in Metro Manila and Cebu. Evidence for General Santos or Mindanao is not found. Assumption, validate via local student org playtests.

## Group play, barkada and classroom use

- No sourced statistics on barkada play habits, icebreaker use or family game nights were found.
- Assumption: friends meet at tables at school, home and cafes and often use phones in parallel. Validate by observing playtests and asking one question per session.
- Assumption: student orgs need short, low-prep icebreakers for 4 to 8 people. Validate with at least one org session before launch.
- Assumption: families play when the activity needs no setup cost. Validate with one family playtest.
- Constraint to respect: DeskTop supports 1 to 4 players per table (PRD). Larger classes need table groups.

## Language: Taglish and code-switching

- Tagalog-English code-switching is widespread in Philippine TV and education [S15].
- One advertising study found 51 percent of words code-switched to English [S15]. This is a media sample, not a population rate.
- English and Filipino are the official languages [S1].
- Assumption: speech recognition handles Taglish game commands reliably in noisy rooms. PRD cites Meta docs for support, not an accuracy figure. Validate with the PRD section 18 voice tests.
- Regional languages such as Cebuano and Hiligaynon are spoken widely in Mindanao and the Visayas. Not sourced here. Assumption: tap controls cover players who prefer those languages.

## Filipino diaspora

- The CFO estimated about 10.2 million overseas Filipinos as of Dec 2013, across permanent, temporary and irregular categories [S8].
- The PSA reported 2.16 million OFWs in Apr to Sep 2023 [S9]. OFWs are a subset of overseas Filipinos.
- A newer CFO total was not retrieved. Do not use the 2013 figure as current without noting its year.
- Assumption: diaspora families want folklore content that reaches children in a shared activity. Validate with a small diaspora playtest over video call.
- Note: DeskTop is Windows only, requires an API key, and ships via GitHub. These limit diaspora reach in the first release.

## Interest in Filipino folklore media

- Trese, a Filipino comic adapted to Netflix in June 2021, features tikbalang, aswang, nuno and santelmo [S14].
- Trese reached No. 1 in the Philippines on Netflix and held it for 10 straight days [S14].
- Local games use the same creatures, including Good Knight on Steam Early Access with tikbalang, kapre and aswang [S17].
- Conclusion: folklore is a proven draw in Filipino media. No data was found on folklore-themed tabletop sales.

## Philippine game development scene

- GDAP, founded in 2007, is the trade body for Philippine studios [S16].
- Around 2014 it cited about 60 studios and about 3,500 employees [S16]. Data is old.
- Local indie titles use folklore. See competitive-landscape.md.
- Annual PGDX event hosts local developers and a board game presence [S11].
- Use: GDAP and PGDX are credible post-hackathon outreach targets. Not a claim of endorsement.

## Implications for DeskTop

- Impact framing: lead with the sourced gap. Filipinos are heavily online on phones (98.6 percent smartphone ownership [S4]) while DeskTop pulls a group back to one table. State this as design intent, not a measured outcome.
- Impact framing: use Trese and local folklore games as proof of appetite for the theme [S14] [S17]. Do not cite market size vendors as proof of demand for DeskTop.
- Demo: show a plain desk, a laptop, a webcam on a stand and one A4 sheet. This answers the device question on camera.
- Demo: show Taglish voice commands plus the tap fallback, since regional language and noise are real risks.
- Launch: start with college barkadas and student orgs in General Santos and nearby campuses, then Metro Manila board game cafes and events such as All aBOARD and Mimic Manila as secondary stages.
- Launch: state hardware needs honestly. Laptop use is common, household computers less so [S4] [S5].
- Avoid: any claim of a measured Philippine market for this genre. None exists in the sources.

## Open questions

- What share of target students own a working Windows laptop and webcam today. Needs a newer source or a campus survey.
- What is the current CFO overseas Filipino total.
- How many Filipino PC gamers play social or co-op games at one table.
- Do General Santos and Mindanao groups play tabletop games, and where.
- Do student orgs and teachers accept an AI-run, API-key-based game in an icebreaker.
- Does the $0.50 per night cost matter to student groups or is the API-key step the larger barrier.

## Sources

| ID | Title | URL | Accessed |
|---|---|---|---|
| S1 | The Filipino Game Market, Allcorrect Games | https://allcorrectgames.com/insights/the-filipino-game-market/ | 2026-10-28 |
| S2 | Philippines Gaming and Mobile Entertainment Market, Ken Research | https://www.kenresearch.com/industry-reports/philippines-gaming-and-mobile-entertainment-market | 2026-10-28 |
| S3 | Philippine Gaming Market Report (August 2026), Back2Gaming | https://www.back2gaming.com/games/philippine-gaming-market-report-august-2026/ | 2026-10-28 |
| S4 | Digital 2026: The Philippines, DataReportal | https://datareportal.com/reports/digital-2026-philippines | 2026-10-28 |
| S5 | PIDS InfoBits on computer ownership (2018 FIES) | https://pids.gov.ph/details/resource/infographics-infobits/infobits-on-computer-ownership-in-ph | 2026-10-28 |
| S6 | SWS: 58 percent of Filipino students used devices for distance learning, Inquirer | https://newsinfo.inquirer.net/1402235/sws-58-of-pinoy-students-used-devices-for-distance-learning/amp | 2026-10-28 |
| S7 | Philippines climbs in Ookla rankings, Aug 2026 | https://pro.edgex.exchange/en-US/news/article/philippines-climbs-ookla-speed-rankings-august-2026 | 2026-10-28 |
| S8 | 2014 CFO Compendium of Statistics on International Migration | https://gad.cfo.gov.ph/wp-content/uploads/2025/01/2014-CFO-Compendium-of-Statistics-on-International-Migration.pdf | 2026-10-28 |
| S9 | Number of OFWs surges to 2.16M in 2023, Manila Times | https://manilatimes.net/2024/09/16/news/national/number-of-ofws-surges-to-216m-in-2023/1971631 | 2026-10-28 |
| S10 | Philippines Board Games Market, IMARC | https://www.imarcgroup.com/philippines-board-games-market | 2026-10-28 |
| S11 | Board game cafes and festivals in Metro Manila (Nerdist, SPOT.ph, Walastech search results) | https://old.spot.ph/eatdrink/the-latest-eat-drink/78694/boardgame-cafes-2019-a2939-20190827-lfrm2 | 2026-10-28 |
| S12 | QC aspires to become board game capital of Southeast Asia, ABS-CBN | https://abs-cbn.com/lifestyle/2025/5/30/qc-aspires-to-become-board-game-capital-of-southeast-asia-1423 | 2026-10-28 |
| S13 | Mimic Manila 2026 TTRPG convention | https://www.fixgamingchannel.com/mimic-manila-2026-ttrpg-convention-makati/ | 2026-10-28 |
| S14 | Netflix animation Trese brings Filipino supernatural beings to screens, Global Voices | https://globalvoices.org/2021/08/11/netflix-animation-trese-brings-filipino-supernatural-beings-into-the-screens/ | 2026-10-28 |
| S15 | Tagalog-English code-switching on Filipino television | https://usurj.journals.usask.ca/article/view/763 | 2026-10-28 |
| S16 | Game Developers Association Philippines, Outsource Accelerator | https://www.outsourceaccelerator.com/glossary/game-developers-association-philippines/ | 2026-10-28 |
| S17 | Pinoy-made game Good Knight on Steam Early Access, GMA | https://gmanetwork.com/news/scitech/technology/809092/pinoy-made-game-good-knight-is-on-sale-available-on-steam-early-access/story | 2026-10-28 |

Notes on source quality: the Trese No. 1 claim in [S14] was reported in search results from several outlets, and the exact page quote was not re-verified. The S8 figure of 10.2 million was confirmed via search summary of the CFO stock estimate, and the compendium PDF was not opened in full. S11 is a search-result aggregate and individual cafe claims should be re-checked before public use.
