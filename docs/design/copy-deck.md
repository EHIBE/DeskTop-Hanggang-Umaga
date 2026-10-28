---
title: Copy deck
purpose: Every player-facing string key with Taglish and English text, plus the GM line bank and card template
read_when: [adding or changing any player-facing text, building lib/copy.ts or assets/lines.json]
canonical_for: [copy keys, line bank, unit card template]
sources: [docs/DeskTop_PRD.md#copy-deck, docs/DeskTop_PRD.md#content-list, docs/DeskTop_PRD.md#14-edge-cases-and-failure-handling]
status: active
last_verified: 2026-10-28
related: [docs/design/cultural-care.md, docs/architecture/ai-contracts.md]
---

# Copy deck

All player-facing text, keyed. This file is canonical until `app/src/renderer/src/lib/copy.ts` and `assets/lines.json` exist, then those files are canonical and this file mirrors them.

## Key facts

| Fact | Value |
|---|---|
| UI keys | 48 from PRD plus 32 Proposed |
| Line bank moments | 14 |
| Placeholders | [name], [unit], [object], [player], [feature], [HP], [n], [action], [target], [pangalan] |
| Review | 2 Filipino playtesters review every Taglish line before recording |
| Process | Add keys with the `desktop-add-copy-key` skill |

## UI copy (PRD section 11)

| Key | Taglish | English |
|---|---|---|
| start.ready | Handa na ba ang mesa? Linisin muna, tapos pindutin ang Start Night. | Is the table ready? Clear it, then press Start Night. |
| calib.place | Ilagay ang isang A4 na papel sa gitna ng mesa. | Place one A4 sheet in the middle of the desk. |
| calib.tap | I-tap ang apat na kanto ng papel. | Tap the four corners of the sheet. |
| calib.done | Ayos! Kita ko na ang buong mesa. | Got it. I can see the whole table. |
| calib.dark | Masyadong madilim. Dagdagan ang ilaw. | Too dark. Add more light. |
| summon.prompt | Maglagay ng isang bagay at sabihin kung ano siya. | Place one object and say what it is. |
| summon.kubo_first | Kailangan muna ng bahay kubo. Ano ang poprotektahan natin? | You need a bahay kubo first. What are we protecting? |
| summon.new_unit | Bagong kakampi: [name]! | New ally: [name]! |
| summon.which | Alin ang bago? I-tap mo. | Which one is new? Tap it. |
| summon.full | Puno na ang baryo. Hanggang 12 lang. | The barrio is full. 12 objects max. |
| summon.stack | Huwag ipatong ang mga piyesa. | Don't stack the pieces. |
| claim.prompt | Isa-isa: "Ako si [pangalan], hawak ko ang..." | One at a time: "I'm [name], I hold..." |
| claim.who | Sino 'yon? I-tap ang pangalan mo. | Who was that? Tap your name. |
| night.start | Lumulubog na ang araw. Hanggang umaga, kapit lang! | The sun is setting. Hold on until morning! |
| move.too_far | Too far! Ibalik mo. | Too far! Move it back. |
| endturn.blocked | May piyesang lumampas. Ibalik muna bago tapusin. | A piece moved too far. Fix it before ending the turn. |
| endturn.checking | Sandali, tinitingnan ko ang mesa... | Hold on, checking the table... |
| endturn.hands | Tanggalin muna ang kamay sa mesa. | Hands off the table first. |
| cmd.heard | [unit] → [action] sa [target]. Sabihin "hindi" para ikansela. | [unit] → [action] on [target]. Say "hindi" to cancel. |
| cmd.cancel | Sige, kinansela. | Okay, canceled. |
| cmd.unknown | Di ko nakuha. Ulitin mo o i-tap na lang. | Didn't catch that. Say it again or tap. |
| cmd.overlap | Isa-isa lang! | One at a time! |
| cmd.no_atk | Walang atake si [unit]. | [unit] can't attack. |
| track.uncertain | Hindi ko sigurado kung nasaan si [unit]. I-tap mo siya. | I'm not sure where [unit] is. Tap it. |
| track.similar | Magkamukha ang dalawang ito. I-tap kung alin si [unit]. | These two look alike. Tap which one is [unit]. |
| lost.out | Ang [unit] ay nawala sa gubat! | [unit] got lost in the forest! |
| lost.back | Bumalik si [unit]! | [unit] is back! |
| enemy.dodge | Nakaiwas! | Dodged! |
| tik.push | Tinulak ng tikbalang si [unit]! Usugin ang [object] sa may anino. | The tikbalang shoved [unit]! Slide the [object] onto the shadow. |
| duw.steal | Ninakaw ng duwende si [unit]! Tanggalin muna sa mesa. | The duwende stole [unit]! Take it off the table. |
| duw.back | Nabawi si [unit]! Ibalik sa may marka. | [unit] is free! Put it back on the mark. |
| duw.escape | Nakatakas ang duwende kasama si [unit]. | The duwende escaped with [unit]. |
| kapre.smoke | Usok ng kapre! Di ko makita ang nasa loob. | Kapre smoke! I can't see inside it. |
| mana.split | Humiwalay ang katawan! Hanapin ang ibabang kalahati! | It split in two! Find the lower half! |
| kubo.hit | Tinamaan ang kubo! [HP] na lang. | The kubo was hit! [HP] left. |
| unit.down | Bagsak si [unit]. | [unit] is down. |
| win | Sumikat na ang araw! Ligtas ang baryo. | The sun is up. The barrio is safe. |
| lose | Nasira ang kubo... Subukan ulit bukas ng gabi. | The kubo fell... Try again tomorrow night. |
| rec.consent | Ire-record ang gabing ito para sa replay. Payag ba lahat? | Tonight will be recorded for the replay. Does everyone agree? |
| rec.on | Nagre-record | Recording |
| replay.making | Ginagawa ang replay... | Making the replay... |
| net.slow | Medyo mabagal ang koneksyon. Tuloy pa rin tayo. | The connection is slow. We'll keep going. |
| net.down | Offline muna ang [feature]. Gamitin ang tap controls. | [feature] is offline. Use tap controls. |
| credits.low | Paubos na ang credits. Naka-Demo Safe Mode na. | Credits are running low. Demo Safe Mode is on. |
| cam.moved | Gumalaw ang camera! I-calibrate ulit. | The camera moved! Calibrate again. |
| player.left | Sino'ng hahawak sa mga piyesa ni [player]? | Who will take [player]'s pieces? |
| restore | Sandali, ibinabalik ko ang laro... | Hold on, restoring the game... |
| welcome_back | Welcome back, [unit]. Kulang ng [n] HP mula kagabi. | Welcome back, [unit]. [n] HP short from last night. |

`lost.out` and `lost.back` stay reserved while F22 is cut. `kapre.smoke` stays reserved while smoke is cut. `welcome_back` needs F16 (Could).

## Proposed keys (lines in the PRD without a key)

English text for these is a proposal for playtester review.

| Key | Taglish (PRD text) | English (proposed) | PRD source |
|---|---|---|---|
| calib.aim | Itutok ang camera sa mesa lang. | Point the camera at the table only. | Section 13 content safety |
| cam.busy | May ibang app na gumagamit ng camera. | Another app is using the camera. | Edge case 30 |
| kubo.moved | Huwag galawin ang kubo! | Don't move the kubo! | Edge case 19 |
| tik.thrown | Itinapon ng tikbalang si [unit] sa gubat! | The tikbalang threw [unit] into the forest! | Edge case 21 |
| effect.timeout | Sige, pwede na. | Okay, that works. | Edge case 22 |
| voice.reclaim | Sabihin ulit ang pangalan ninyo, isa-isa. | Say your names again, one at a time. | Edge case 27 |
| net.offline | Offline muna ang [feature]. Tuloy pa rin tayo. | [feature] is offline for now. We'll keep going. | Flow F10 |
| key.prompt | I-paste ang Meta Model API key mo. | Paste your Meta Model API key. | M3 app shell, playtester review |
| key.label | API key | API key | M3, playtester review |
| key.save | I-save | Save | M3, playtester review |
| key.saved | Na-save na ang key. | Key saved. | M3, playtester review |
| key.invalid | Hindi gumana ang key. Subukan ulit. | That key did not work. Try again. | M3, playtester review |
| key.privacy | Naka-encrypt ang key sa laptop na ito. Ang game backend lang ang nakakabasa. | The key is stored encrypted on this laptop. Only the game backend reads it. | M3, playtester review |
| key.offline | Maglaro offline gamit ang Demo Safe Mode | Play offline with Demo Safe Mode | M3, playtester review |
| start.new | Bagong Kampanya | New Campaign | M3, playtester review |
| start.continue | Ituloy ang Kampanya | Continue Campaign | M3, playtester review |
| start.name | Pangalan ng baryo | Barrio name | M3, playtester review |
| start.difficulty | Hirap | Difficulty | M3, playtester review |
| start.demo_safe | Demo Safe Mode | Demo Safe Mode | M3, playtester review |
| start.empty | Wala pang na-save na kampanya. | No saved campaigns yet. | M3, playtester review |
| start.begin | Start Night | Start Night | M3, playtester review |
| start.nights | Gabing nalampasan: [n] | Nights survived: [n] | M3, playtester review |
| diff.madali | Madali | Easy | M3, playtester review |
| diff.normal | Normal | Normal | M3, playtester review |
| diff.mahirap | Mahirap | Hard | M3, playtester review |
| calib.camera | Pumili ng camera | Pick a camera | M3, playtester review |
| calib.no_camera | Walang nakitang camera. | No camera found. | M3, playtester review |
| calib.reset | Ulitin ang mga kanto | Redo the corners | M3, playtester review |
| calib.remove | Alisin ang papel, tapos pindutin ang Tapos na. | Remove the sheet, then press Done. | M3, playtester review |
| calib.confirm | Tapos na | Done | M3, playtester review |
| calib.width | Lapad (cm) | Width (cm) | M3, playtester review |
| calib.height | Taas (cm) | Height (cm) | M3, playtester review |
| summon.need_units | Kailangan pa ng hindi bababa sa 2 kakampi bukod sa kubo. | Need at least 2 more allies besides the kubo. | M4, Proposed, playtester review |
| summon.name_label | Pangalan ng bagay | Name of the object | M4, Proposed, playtester review |
| summon.name_go | Sige | Go | M4, Proposed, playtester review |
| summon.busy | Sandali... | One moment... | M4, Proposed, playtester review |
| summon.reroll | Ulitin ang card | Re-roll card | M4, Proposed, playtester review |
| summon.rename | Palitan ang pangalan | Rename | M4, Proposed, playtester review |
| summon.rename_save | I-save | Save | M4, Proposed, playtester review |
| summon.begin | Begin Night | Begin Night | M4, Proposed, playtester review |
| summon.roster | Mga kakampi | Allies | M4, Proposed, playtester review |
| summon.close | Isara | Close | M4, Proposed, playtester review |
| card.owner_none | Wala pa | None yet | M4, Proposed, playtester review |
| card.owner | Hawak ni | Owner | M4, Proposed, playtester review |
| card.power | Kapangyarihan | Power | M4, Proposed, playtester review |
| card.move | Galaw | Move | M4, Proposed, playtester review |
| card.range | Abot | Reach | M4, Proposed, playtester review |
| card.class | Uri | Class | M4, Proposed, playtester review |
| class.kubo | Kubo | Kubo, the objective | M4, Proposed, playtester review |
| class.charm | Anting | Charm, passive support | M4, Proposed, playtester review |
| class.healer | Manggagamot | Healer | M4, Proposed, playtester review |
| class.fighter | Mandirigma | Fighter | M4, Proposed, playtester review |
| class.reach | Sibat | Reach, long melee | M4, Proposed, playtester review |
| class.ranged | Pana | Ranged | M4, Proposed, playtester review |
| class.scout | Sugo | Scout | M4, Proposed, playtester review |
| class.wall | Hadlang | Wall | M4, Proposed, playtester review |
| move.none | Wala | None | M4, Proposed, playtester review |
| move.short | Maikli | Short | M4, Proposed, playtester review |
| move.medium | Katamtaman | Medium | M4, Proposed, playtester review |
| move.long | Malayo | Long | M4, Proposed, playtester review |
| range.none | Wala | None | M4, Proposed, playtester review |
| range.melee | Lapit | Melee | M4, Proposed, playtester review |
| range.reach | Abot | Reach | M4, Proposed, playtester review |
| range.far | Layo | Far | M4, Proposed, playtester review |
| power.none | Wala | None | M4, Proposed, playtester review |
| power.P01 | Gamot | Heal an ally within 10 cm for 2 HP. | M4, Proposed, playtester review |
| power.P02 | Kalasag | An ally within 10 cm absorbs the next 2 damage. | M4, Proposed, playtester review |
| power.P03 | Tulak | Push an enemy in melee 8 cm away. | M4, Proposed, playtester review |
| power.P04 | Tigil | An enemy in range skips its next attack. | M4, Proposed, playtester review |
| power.P05 | Hampas | 1 damage to every enemy within 6 cm. | M4, Proposed, playtester review |
| power.P06 | Bantay | The kubo absorbs the next 3 damage. | M4, Proposed, playtester review |
| power.P07 | Taboy | Enemies cannot end a move within 8 cm. | M4, Proposed, playtester review |
| power.P08 | Liwanag | Clears smoke within 12 cm. | M4, Proposed, playtester review |
| power.P09 | Tusok | Hits the target and one more enemy behind it. | M4, Proposed, playtester review |
| power.P10 | Sigaw | Allies within 10 cm get +1 ATK this turn. | M4, Proposed, playtester review |
| power.P11 | Habol | +2 damage against a duwende in melee. | M4, Proposed, playtester review |
| power.P12 | Asin | 3 damage to a manananggal lower half. | M4, Proposed, playtester review |
| cost.label | Nagastos na credits | Credits spent | M5, Proposed, playtester review |
| hud.turn | GABI [n] / 8 | NIGHT [n] / 8 | M7 to M8, Proposed, playtester review |
| phase.spawn | Dumarating sila | They are coming | M7 to M8, Proposed, playtester review |
| phase.player | Galaw at Utos | Move and give orders | M7 to M8, Proposed, playtester review |
| phase.check | Sinusuri | Checking | M7 to M8, Proposed, playtester review |
| phase.battle | Labanan | Battle | M7 to M8, Proposed, playtester review |
| phase.paused | Naka-pause | Paused | M7 to M8, Proposed, playtester review |
| hud.kubo | Kubo | Kubo | M7 to M8, Proposed, playtester review |
| hud.hp | HP | HP | M7 to M8, Proposed, playtester review |
| hud.cd | CD | Cooldown | M7 to M8, Proposed, playtester review |
| hud.down | Bagsak | Down | M7 to M8, Proposed, playtester review |
| hud.stunned | Nakatigil | Stunned | M7 to M8, Proposed, playtester review |
| hud.orders | Mga Utos | Orders | M7 to M8, Proposed, playtester review |
| hud.no_orders | Wala pang utos. I-tap ang kakampi o magsalita. | No orders yet. Tap an ally or speak. | M7 to M8, Proposed, playtester review |
| hud.end_turn | TAPOS / END TURN | End turn | M7 to M8, Proposed, playtester review |
| hud.recalibrate | I-calibrate ulit | Recalibrate | M7 to M8, Proposed, playtester review |
| hud.chip_cancel | Kanselahin ang utos | Cancel order | M7 to M8, Proposed, playtester review |
| hud.board | Mesa ng laban | Battle board | M7 to M8, Proposed, playtester review |
| act.attack | atake | attack | M7 to M8, Proposed, playtester review |
| act.heal | gamot | heal | M7 to M8, Proposed, playtester review |
| chip.text | [unit] → [action] sa [target] | [unit] → [action] on [target] | M7 to M8, Proposed, playtester review |
| chip.self | [unit] → [action] | [unit] → [action] | M7 to M8, Proposed, playtester review |
| tap.attack | Atake | Attack | M7 to M8, Proposed, playtester review |
| tap.heal | Gamot | Heal | M7 to M8, Proposed, playtester review |
| tap.cancel | Kansela | Cancel | M7 to M8, Proposed, playtester review |
| tap.pick_action | Utos para kay [unit]: | Order for [unit]: | M7 to M8, Proposed, playtester review |
| tap.pick_target | I-tap ang target ni [unit]. | Tap a target for [unit]. | M7 to M8, Proposed, playtester review |
| enemy.aswang | Aswang | Aswang | M7 to M8, Proposed, playtester review |
| enemy.tikbalang | Tikbalang | Tikbalang | M7 to M8, Proposed, playtester review |
| enemy.kapre | Kapre | Kapre | M7 to M8, Proposed, playtester review |
| enemy.manananggal | Manananggal | Manananggal | M7 to M8, Proposed, playtester review |
| enemy.duwende | Duwende | Duwende | M7 to M8, Proposed, playtester review |
| enemy.upper | Itaas | Upper | M7 to M8, Proposed, playtester review |
| enemy.lower | Ibaba | Lower | M7 to M8, Proposed, playtester review |
| claim.players | Mga manlalaro | Players | M7 to M8, Proposed, playtester review |
| claim.name_label | Manlalaro [n] | Player [n] | M7 to M8, Proposed, playtester review |
| claim.done | Tapos na | Done | M7 to M8, Proposed, playtester review |
| claim.skip | Laktawan | Skip | M7 to M8, Proposed, playtester review |
| claim.tap_unit | I-tap ang piyesa, tapos ang pangalan. | Tap a piece, then a name. | M7 to M8, Proposed, playtester review |
| claim.duplicate | Magkaiba dapat ang mga pangalan. | Names must be different. | M7 to M8, Proposed, playtester review |
| score.alive | Buhay na kakampi | Allies alive | M7 to M8, Proposed, playtester review |
| score.kubo | HP ng kubo | Kubo HP | M7 to M8, Proposed, playtester review |
| score.defeated | Natalong kalaban | Enemies defeated | M7 to M8, Proposed, playtester review |
| score.total | Kabuuan | Total | M7 to M8, Proposed, playtester review |
| score.bayani | Bayani ng Gabi | Hero of the Night | M7 to M8, Proposed, playtester review |
| score.bayani_none | Wala ngayong gabi | None tonight | M7 to M8, Proposed, playtester review |
| sunrise.title | SUMIKAT NA | SUNRISE | M7 to M8, Proposed, playtester review |
| sunrise.next | Susunod na Gabi | Next Night | M7 to M8, Proposed, playtester review |
| sunrise.quit | Umalis | Quit | M7 to M8, Proposed, playtester review |
| defeat.title | NASIRA ANG KUBO | THE KUBO FELL | M7 to M8, Proposed, playtester review |
| defeat.retry | Subukan Ulit | Try Again | M7 to M8, Proposed, playtester review |

## GM line bank (local fallback and Spark style reference)

Goes into `assets/lines.json`.

| Moment | Taglish | English caption |
|---|---|---|
| night_start | Lumulubog na ang araw. Hanggang umaga, kapit lang! | The sun is setting. Hold on until morning! |
| tabi_tabi | Narinig ka ng mga duwende. Mukhang mabait sila ngayong gabi. | The duwende heard you. They seem kind tonight. |
| spawn_aswang | May aswang na paparating mula sa hilaga. Bantayan ang nag-iisa! | An aswang is coming from the north. Watch whoever is alone! |
| spawn_tikbalang | Ramdam mo ba 'yung yabag? Tikbalang 'yan. | Feel those footsteps? That's a tikbalang. |
| spawn_kapre | Amoy tabako... may kapre sa puno. | Smells like tobacco... there's a kapre in the tree. |
| spawn_manananggal | Tumingala kayo. May lumilipad. | Look up. Something is flying. |
| spawn_duwende | Ingat sa anting-anting, may maliit na kamay na gustong humawak. | Guard the charm, a little hand wants it. |
| hit | Tinamaan! Ganyan nga! | Hit! That's it! |
| dodge | Nakaiwas! Muntik na. | Dodged! That was close. |
| kubo_hit | Tinamaan ang kubo! [HP] na lang. | The kubo was hit! [HP] left. |
| unit_down | Bagsak si [unit]. Bawi tayo. | [unit] is down. Let's get it back. |
| last_turn | Huling dilim na. Konting tiis na lang! | Last stretch of dark. Just a little longer! |
| win | Sumikat na ang araw! Ligtas ang baryo. | The sun is up. The barrio is safe. |
| lose | Nasira ang kubo... Subukan ulit bukas ng gabi. | The kubo fell... Try again tomorrow night. |

The aswang spawn line names "hilaga" (north). Pick the line variant by spawn edge, or add edge variants for east, south and west before recording (Unverified, PRD gives only north).

## Unit card template

```text
[Sprite]  [Unit name]            Class: [class]
HP [n]  ATK [n]  Galaw: [Maikli|Katamtaman|Malayo]  Abot: [Lapit|Abot|Layo]
Kapangyarihan: [power_name_tl]: [card_text_tl]
EN: [card_text_en]
Owner: [player or "Wala pa"]
```

## Writing rules

- Taglish the way young Filipinos talk with friends. Max 2 short sentences per line.
- Every line has an English caption.
- No gore, slurs, politics, religion jokes, or real place names tied to monsters (`cultural-care.md`).
- Player-entered names pass the profanity filter before they show.
