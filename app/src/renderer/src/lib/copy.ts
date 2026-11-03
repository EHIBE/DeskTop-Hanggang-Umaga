import { currentLang } from './lang'
import type { CopyParams } from './types'

export type CopyEntry = Readonly<{ tl: string; en: string }>

const entries = {
  'start.ready': {
    tl: 'Handa na ba ang mesa? Linisin muna, tapos pindutin ang Start Night.',
    en: 'Is the table ready? Clear it, then press Start Night.'
  },
  'calib.place': {
    tl: 'Ilagay ang isang A4 na papel sa gitna ng mesa.',
    en: 'Place one A4 sheet in the middle of the desk.'
  },
  'calib.tap': {
    tl: 'I-tap ang apat na kanto ng papel.',
    en: 'Tap the four corners of the sheet.'
  },
  'calib.done': {
    tl: 'Ayos! Kita ko na ang buong mesa.',
    en: 'Got it. I can see the whole table.'
  },
  'calib.dark': { tl: 'Masyadong madilim. Dagdagan ang ilaw.', en: 'Too dark. Add more light.' },
  'summon.prompt': {
    tl: 'Maglagay ng isang bagay at sabihin kung ano siya.',
    en: 'Place one object and say what it is.'
  },
  'summon.kubo_first': {
    tl: 'Kailangan muna ng bahay kubo. Ano ang poprotektahan natin?',
    en: 'You need a bahay kubo first. What are we protecting?'
  },
  'summon.new_unit': { tl: 'Bagong kakampi: [name]!', en: 'New ally: [name]!' },
  'summon.which': { tl: 'Alin ang bago? I-tap mo.', en: 'Which one is new? Tap it.' },
  'summon.full': {
    tl: 'Puno na ang baryo. Hanggang 12 lang.',
    en: 'The barrio is full. 12 objects max.'
  },
  'summon.stack': { tl: 'Huwag ipatong ang mga piyesa.', en: "Don't stack the pieces." },
  'claim.prompt': {
    tl: 'Isa-isa: "Ako si [pangalan], hawak ko ang..."',
    en: 'One at a time: "I\'m [name], I hold..."'
  },
  'claim.who': { tl: "Sino 'yon? I-tap ang pangalan mo.", en: 'Who was that? Tap your name.' },
  'night.start': {
    tl: 'Lumulubog na ang araw. Hanggang umaga, kapit lang!',
    en: 'The sun is setting. Hold on until morning!'
  },
  'move.too_far': { tl: 'Too far! Ibalik mo.', en: 'Too far! Move it back.' },
  'endturn.blocked': {
    tl: 'May piyesang lumampas. Ibalik muna bago tapusin.',
    en: 'A piece moved too far. Fix it before ending the turn.'
  },
  'endturn.checking': {
    tl: 'Sandali, tinitingnan ko ang mesa...',
    en: 'Hold on, checking the table...'
  },
  'endturn.hands': {
    tl: 'Tanggalin muna ang kamay sa mesa.',
    en: 'Hands off the table first.'
  },
  'cmd.heard': {
    tl: '[unit] → [action] sa [target]. Sabihin "hindi" para ikansela.',
    en: '[unit] → [action] on [target]. Say "hindi" to cancel.'
  },
  'cmd.cancel': { tl: 'Sige, kinansela.', en: 'Okay, canceled.' },
  'cmd.unknown': {
    tl: 'Di ko nakuha. Ulitin mo o i-tap na lang.',
    en: "Didn't catch that. Say it again or tap."
  },
  'cmd.overlap': { tl: 'Isa-isa lang!', en: 'One at a time!' },
  'cmd.no_atk': { tl: 'Walang atake si [unit].', en: "[unit] can't attack." },
  'track.uncertain': {
    tl: 'Hindi ko sigurado kung nasaan si [unit]. I-tap mo siya.',
    en: "I'm not sure where [unit] is. Tap it."
  },
  'track.similar': {
    tl: 'Magkamukha ang dalawang ito. I-tap kung alin si [unit].',
    en: 'These two look alike. Tap which one is [unit].'
  },
  'lost.out': { tl: 'Ang [unit] ay nawala sa gubat!', en: '[unit] got lost in the forest!' },
  'lost.back': { tl: 'Bumalik si [unit]!', en: '[unit] is back!' },
  'enemy.dodge': { tl: 'Nakaiwas!', en: 'Dodged!' },
  'tik.push': {
    tl: 'Tinulak ng tikbalang si [unit]! Usugin ang [object] sa may anino.',
    en: 'The tikbalang shoved [unit]! Slide the [object] onto the shadow.'
  },
  'duw.steal': {
    tl: 'Ninakaw ng duwende si [unit]! Tanggalin muna sa mesa.',
    en: 'The duwende stole [unit]! Take it off the table.'
  },
  'duw.back': {
    tl: 'Nabawi si [unit]! Ibalik sa may marka.',
    en: '[unit] is free! Put it back on the mark.'
  },
  'duw.escape': {
    tl: 'Nakatakas ang duwende kasama si [unit].',
    en: 'The duwende escaped with [unit].'
  },
  'kapre.smoke': {
    tl: 'Usok ng kapre! Di ko makita ang nasa loob.',
    en: "Kapre smoke! I can't see inside it."
  },
  'mana.split': {
    tl: 'Humiwalay ang katawan! Hanapin ang ibabang kalahati!',
    en: 'It split in two! Find the lower half!'
  },
  'kubo.hit': { tl: 'Tinamaan ang kubo! [HP] na lang.', en: 'The kubo was hit! [HP] left.' },
  'unit.down': { tl: 'Bagsak si [unit].', en: '[unit] is down.' },
  win: { tl: 'Sumikat na ang araw! Ligtas ang baryo.', en: 'The sun is up. The barrio is safe.' },
  lose: {
    tl: 'Nasira ang kubo... Subukan ulit bukas ng gabi.',
    en: 'The kubo fell... Try again tomorrow night.'
  },
  'rec.consent': {
    tl: 'Ire-record ang gabing ito para sa replay. Payag ba lahat?',
    en: 'Tonight will be recorded for the replay. Does everyone agree?'
  },
  'rec.on': { tl: 'Nagre-record', en: 'Recording' },
  'rec.agree': { tl: 'Payag', en: 'I agree' },
  'rec.decline': { tl: 'Hindi', en: 'No' },
  'rec.unavailable': {
    tl: 'Walang recording ngayon, tuloy pa rin ang laro.',
    en: 'No recording tonight, the game goes on.'
  },
  'rec.no_ok': {
    tl: 'Okay lang ang Hindi. Tuloy pa rin ang gabi, walang recording.',
    en: 'Saying no is fine. The night still plays, just without recording.'
  },
  'rec.waiting': { tl: 'Wala pang sagot', en: 'No answer yet' },
  'rec.player': { tl: 'Sagot ni [name]', en: "[name]'s answer" },
  'replay.making': { tl: 'Ginagawa ang replay...', en: 'Making the replay...' },
  'replay.make': { tl: 'Gawin ang Replay', en: 'Make the Replay' },
  'replay.done': { tl: 'Handa na ang replay!', en: 'The replay is ready!' },
  'replay.failed': {
    tl: 'Hindi nagawa ang replay. Subukan ulit.',
    en: 'Could not make the replay. Try again.'
  },
  'replay.none': {
    tl: 'Walang recording ngayong gabi, kaya walang replay.',
    en: 'No recording tonight, so no replay.'
  },
  'replay.no_ffmpeg': {
    tl: 'Kailangan ng ffmpeg para sa replay. I-install muna.',
    en: 'The replay needs ffmpeg. Install it first.'
  },
  'replay.show': { tl: 'Ipakita sa folder', en: 'Show in folder' },
  'replay.missing': { tl: 'Hindi makita ang file.', en: 'Could not find the file.' },
  'net.slow': {
    tl: 'Medyo mabagal ang koneksyon. Tuloy pa rin tayo.',
    en: "The connection is slow. We'll keep going."
  },
  'net.down': {
    tl: 'Offline muna ang [feature]. Gamitin ang tap controls.',
    en: '[feature] is offline. Use tap controls.'
  },
  'cost.label': { tl: 'Nagastos na credits', en: 'Credits spent' },
  'credits.low': {
    tl: 'Paubos na ang credits. Naka-Demo Safe Mode na.',
    en: 'Credits are running low. Demo Safe Mode is on.'
  },
  'cam.moved': {
    tl: 'Gumalaw ang camera! I-calibrate ulit.',
    en: 'The camera moved! Calibrate again.'
  },
  'player.left': {
    tl: "Sino'ng hahawak sa mga piyesa ni [player]?",
    en: "Who will take [player]'s pieces?"
  },
  restore: {
    tl: 'Sandali, ibinabalik ko ang laro...',
    en: 'Hold on, restoring the game...'
  },
  welcome_back: {
    tl: 'Welcome back, [unit]. Kulang ng [n] HP mula kagabi.',
    en: 'Welcome back, [unit]. [n] HP short from last night.'
  },
  'calib.aim': { tl: 'Itutok ang camera sa mesa lang.', en: 'Point the camera at the table only.' },
  'cam.black': {
    tl: 'Itim lang ang kuha ng camerang ito. Baka gamit ito ng ibang app, gaya ng NVIDIA Broadcast. Pumili ng ibang camera.',
    en: 'This camera only shows black. Another app such as NVIDIA Broadcast may be holding it. Pick another camera.'
  },
  'calib.no_picture': { tl: 'walang larawan', en: 'no picture' },
  'cam.busy': {
    tl: 'May ibang app na gumagamit ng camera.',
    en: 'Another app is using the camera.'
  },
  'kubo.moved': { tl: 'Huwag galawin ang kubo!', en: "Don't move the kubo!" },
  'tik.thrown': {
    tl: 'Itinapon ng tikbalang si [unit] sa gubat!',
    en: 'The tikbalang threw [unit] into the forest!'
  },
  'effect.timeout': { tl: 'Sige, pwede na.', en: 'Okay, that works.' },
  'voice.reclaim': {
    tl: 'Sabihin ulit ang pangalan ninyo, isa-isa.',
    en: 'Say your names again, one at a time.'
  },
  'net.offline': {
    tl: 'Offline muna ang [feature]. Tuloy pa rin tayo.',
    en: "[feature] is offline for now. We'll keep going."
  },
  'key.prompt': {
    tl: 'I-paste ang Meta Model API key mo.',
    en: 'Paste your Meta Model API key.'
  },
  'key.label': { tl: 'API key', en: 'API key' },
  'key.save': { tl: 'I-save', en: 'Save' },
  'key.saved': { tl: 'Na-save na ang key.', en: 'Key saved.' },
  'key.invalid': {
    tl: 'Hindi gumana ang key. Subukan ulit.',
    en: 'That key did not work. Try again.'
  },
  'key.privacy': {
    tl: 'Naka-encrypt ang key sa laptop na ito. Ang game backend lang ang nakakabasa.',
    en: 'The key is stored encrypted on this laptop. Only the game backend reads it.'
  },
  'key.offline': {
    tl: 'Maglaro offline gamit ang Demo Safe Mode',
    en: 'Play offline with Demo Safe Mode'
  },
  'start.new': { tl: 'Bagong Kampanya', en: 'New Campaign' },
  'start.continue': { tl: 'Ituloy ang Kampanya', en: 'Continue Campaign' },
  'start.name': { tl: 'Pangalan ng baryo', en: 'Barrio name' },
  'start.difficulty': { tl: 'Hirap', en: 'Difficulty' },
  'start.demo_safe': { tl: 'Demo Safe Mode', en: 'Demo Safe Mode' },
  'start.empty': { tl: 'Wala pang na-save na kampanya.', en: 'No saved campaigns yet.' },
  'start.begin': { tl: 'Start Night', en: 'Start Night' },
  'start.nights': { tl: 'Gabing nalampasan: [n]', en: 'Nights survived: [n]' },
  'start.delete': { tl: 'Burahin', en: 'Delete' },
  'delete.confirm': { tl: 'Sigurado? Burahin na', en: 'Sure? Delete now' },
  'delete.done': { tl: 'Nabura na ang kampanya.', en: 'Campaign deleted.' },
  'delete.failed': {
    tl: 'Hindi nabura ang kampanya. Subukan ulit.',
    en: 'Could not delete the campaign. Try again.'
  },
  'start.demo_safe_sam': { tl: 'SAM re-anchor sa Demo Safe', en: 'SAM re-anchor in Demo Safe' },
  'summon.resume_banner': {
    tl: 'May naka-save na gabi. Itutuloy ito sa turn [turn].',
    en: 'A saved night is waiting. It will continue at turn [turn].'
  },
  'summon.resume_button': { tl: 'Ituloy ang Gabi (turn [turn])', en: 'Resume Night (turn [turn])' },
  'night.pause': { tl: 'Pause', en: 'Pause' },
  'night.resume': { tl: 'Ituloy', en: 'Resume' },
  'night.continue_anyway': { tl: 'Ituloy pa rin', en: 'Continue anyway' },
  'night.cam_hint': {
    tl: 'Baka mali ang posisyon kung hindi muna mag-calibrate.',
    en: 'Positions may be off if you continue without recalibrating.'
  },
  'claim.countdown': {
    tl: 'Sasara ang claim sa [seconds] segundo',
    en: 'Claims close in [seconds] seconds'
  },
  'diff.madali': { tl: 'Madali', en: 'Easy' },
  'diff.normal': { tl: 'Normal', en: 'Normal' },
  'diff.mahirap': { tl: 'Mahirap', en: 'Hard' },
  'calib.camera': { tl: 'Pumili ng camera', en: 'Pick a camera' },
  'calib.no_camera': { tl: 'Walang nakitang camera.', en: 'No camera found.' },
  'calib.reset': { tl: 'Ulitin ang mga kanto', en: 'Redo the corners' },
  'calib.remove': {
    tl: 'Alisin ang papel, tapos pindutin ang Tapos na.',
    en: 'Remove the sheet, then press Done.'
  },
  'calib.confirm': { tl: 'Tapos na', en: 'Done' },
  'calib.width': { tl: 'Lapad (cm)', en: 'Width (cm)' },
  'calib.height': { tl: 'Taas (cm)', en: 'Height (cm)' },
  'summon.need_units': {
    tl: 'Kailangan pa ng hindi bababa sa 2 kakampi bukod sa kubo.',
    en: 'Need at least 2 more allies besides the kubo.'
  },
  'summon.name_label': { tl: 'Pangalan ng bagay', en: 'Name of the object' },
  'summon.name_go': { tl: 'Sige', en: 'Go' },
  'summon.busy': { tl: 'Sandali...', en: 'One moment...' },
  'summon.reroll': { tl: 'Ulitin ang card', en: 'Re-roll card' },
  'summon.rename': { tl: 'Palitan ang pangalan', en: 'Rename' },
  'summon.rename_save': { tl: 'I-save', en: 'Save' },
  'summon.begin': { tl: 'Begin Night', en: 'Begin Night' },
  'summon.roster': { tl: 'Mga kakampi', en: 'Allies' },
  'summon.close': { tl: 'Isara', en: 'Close' },
  'model.spark': { tl: 'Muse Spark 1.3', en: 'Muse Spark 1.3' },
  'model.sam': { tl: 'SAM 3.1', en: 'SAM 3.1' },
  'model.image': { tl: 'Muse Image 1.0', en: 'Muse Image 1.0' },
  'model.voice': { tl: 'Muse Voice Transcribe 1.0', en: 'Muse Voice Transcribe 1.0' },
  'made.title': { tl: 'Paano ginawa ang kakampi', en: 'How the ally was made' },
  'made.show': { tl: 'Ipakita kung paano ginawa', en: 'Show how it was made' },
  'made.spark_step': {
    tl: 'Nahanap ang bagay at isinulat ang card',
    en: 'Found the object and wrote the card'
  },
  'made.fallback_name': { tl: 'Tap o offline', en: 'Tap or offline' },
  'made.fallback_step': {
    tl: 'Hindi ginamit ang Spark. Tap ang ginamit.',
    en: 'Spark was not used. Tap or offline.'
  },
  'made.sam_step': { tl: 'Eksaktong balangkas', en: 'Exact outline' },
  'made.image_step': { tl: 'Pixel sprite', en: 'Pixel sprite' },
  'made.drawing': { tl: 'Ginuguhit...', en: 'Drawing...' },
  'card.owner_none': { tl: 'Wala pa', en: 'None yet' },
  'card.owner': { tl: 'Hawak ni', en: 'Owner' },
  'card.power': { tl: 'Kapangyarihan', en: 'Power' },
  'card.move': { tl: 'Galaw', en: 'Move' },
  'card.range': { tl: 'Abot', en: 'Reach' },
  'card.class': { tl: 'Uri', en: 'Class' },
  'class.kubo': { tl: 'Kubo', en: 'Kubo, the objective' },
  'class.charm': { tl: 'Anting', en: 'Charm, passive support' },
  'class.healer': { tl: 'Manggagamot', en: 'Healer' },
  'class.fighter': { tl: 'Mandirigma', en: 'Fighter' },
  'class.reach': { tl: 'Sibat', en: 'Reach, long melee' },
  'class.ranged': { tl: 'Pana', en: 'Ranged' },
  'class.scout': { tl: 'Sugo', en: 'Scout' },
  'class.wall': { tl: 'Hadlang', en: 'Wall' },
  'move.none': { tl: 'Wala', en: 'None' },
  'move.short': { tl: 'Maikli', en: 'Short' },
  'move.medium': { tl: 'Katamtaman', en: 'Medium' },
  'move.long': { tl: 'Malayo', en: 'Long' },
  'range.none': { tl: 'Wala', en: 'None' },
  'range.melee': { tl: 'Lapit', en: 'Melee' },
  'range.reach': { tl: 'Abot', en: 'Reach' },
  'range.far': { tl: 'Layo', en: 'Far' },
  'power.none': { tl: 'Wala', en: 'None' },
  'power.P01': { tl: 'Gamot', en: 'Heal an ally within 10 cm for 2 HP.' },
  'power.P02': { tl: 'Kalasag', en: 'An ally within 10 cm absorbs the next 2 damage.' },
  'power.P03': { tl: 'Tulak', en: 'Push an enemy in melee 8 cm away.' },
  'power.P04': { tl: 'Tigil', en: 'An enemy in range skips its next attack.' },
  'power.P05': { tl: 'Hampas', en: '1 damage to every enemy within 6 cm.' },
  'power.P06': { tl: 'Bantay', en: 'The kubo absorbs the next 3 damage.' },
  'power.P07': { tl: 'Taboy', en: 'Enemies cannot end a move within 8 cm.' },
  'power.P08': { tl: 'Liwanag', en: 'Clears smoke within 12 cm.' },
  'power.P09': { tl: 'Tusok', en: 'Hits the target and one more enemy behind it.' },
  'power.P10': { tl: 'Sigaw', en: 'Allies within 10 cm get +1 ATK this turn.' },
  'power.P11': { tl: 'Habol', en: '+2 damage against a duwende in melee.' },
  'power.P12': { tl: 'Asin', en: '3 damage to a manananggal lower half.' },
  'hud.turn': { tl: 'GABI [n] / 8', en: 'NIGHT [n] / 8' },
  'phase.spawn': { tl: 'Dumarating sila', en: 'They are coming' },
  'phase.player': { tl: 'Galaw at Utos', en: 'Move and give orders' },
  'phase.check': { tl: 'Sinusuri', en: 'Checking' },
  'phase.battle': { tl: 'Labanan', en: 'Battle' },
  'phase.paused': { tl: 'Naka-pause', en: 'Paused' },
  'hud.kubo': { tl: 'Kubo', en: 'Kubo' },
  'hud.hp': { tl: 'HP', en: 'HP' },
  'hud.cd': { tl: 'CD', en: 'Cooldown' },
  'hud.down': { tl: 'Bagsak', en: 'Down' },
  'hud.stunned': { tl: 'Nakatigil', en: 'Stunned' },
  'hud.orders': { tl: 'Mga Utos', en: 'Orders' },
  'hud.no_orders': {
    tl: 'Wala pang utos. I-tap ang kakampi o magsalita.',
    en: 'No orders yet. Tap an ally or speak.'
  },
  'hud.end_turn': { tl: 'TAPOS / END TURN', en: 'End turn' },
  'hud.recalibrate': { tl: 'I-calibrate ulit', en: 'Recalibrate' },
  'hud.chip_cancel': { tl: 'Kanselahin ang utos', en: 'Cancel order' },
  'hud.board': { tl: 'Mesa ng laban', en: 'Battle board' },
  'act.attack': { tl: 'atake', en: 'attack' },
  'act.heal': { tl: 'gamot', en: 'heal' },
  'chip.text': { tl: '[unit] → [action] sa [target]', en: '[unit] → [action] on [target]' },
  'chip.self': { tl: '[unit] → [action]', en: '[unit] → [action]' },
  'tap.attack': { tl: 'Atake', en: 'Attack' },
  'tap.heal': { tl: 'Gamot', en: 'Heal' },
  'tap.cancel': { tl: 'Kansela', en: 'Cancel' },
  'tap.pick_action': { tl: 'Utos para kay [unit]:', en: 'Order for [unit]:' },
  'tap.pick_target': { tl: 'I-tap ang target ni [unit].', en: 'Tap a target for [unit].' },
  'enemy.aswang': { tl: 'Aswang', en: 'Aswang' },
  'enemy.tikbalang': { tl: 'Tikbalang', en: 'Tikbalang' },
  'enemy.kapre': { tl: 'Kapre', en: 'Kapre' },
  'enemy.manananggal': { tl: 'Manananggal', en: 'Manananggal' },
  'enemy.duwende': { tl: 'Duwende', en: 'Duwende' },
  'enemy.upper': { tl: 'Itaas', en: 'Upper' },
  'enemy.lower': { tl: 'Ibaba', en: 'Lower' },
  'claim.players': { tl: 'Mga manlalaro', en: 'Players' },
  'claim.name_label': { tl: 'Manlalaro [n]', en: 'Player [n]' },
  'claim.done': { tl: 'Tapos na', en: 'Done' },
  'claim.skip': { tl: 'Laktawan', en: 'Skip' },
  'claim.tap_unit': {
    tl: 'I-tap ang piyesa, tapos ang pangalan.',
    en: 'Tap a piece, then a name.'
  },
  'claim.duplicate': { tl: 'Magkaiba dapat ang mga pangalan.', en: 'Names must be different.' },
  'score.alive': { tl: 'Buhay na kakampi', en: 'Allies alive' },
  'score.kubo': { tl: 'HP ng kubo', en: 'Kubo HP' },
  'score.defeated': { tl: 'Natalong kalaban', en: 'Enemies defeated' },
  'score.total': { tl: 'Kabuuan', en: 'Total' },
  'score.bayani': { tl: 'Bayani ng Gabi', en: 'Hero of the Night' },
  'score.bayani_none': { tl: 'Wala ngayong gabi', en: 'None tonight' },
  'sunrise.title': { tl: 'SUMIKAT NA', en: 'SUNRISE' },
  'sunrise.next': { tl: 'Susunod na Gabi', en: 'Next Night' },
  'sunrise.quit': { tl: 'Umalis', en: 'Quit' },
  'defeat.title': { tl: 'NASIRA ANG KUBO', en: 'THE KUBO FELL' },
  'defeat.retry': { tl: 'Subukan Ulit', en: 'Try Again' },
  'narration.mood.kalmado': { tl: 'Kalmado', en: 'Calm' },
  'narration.mood.kaba': { tl: 'Kaba', en: 'Tense' },
  'narration.mood.takot': { tl: 'Takot', en: 'Fear' },
  'narration.mood.tagumpay': { tl: 'Tagumpay', en: 'Triumph' },
  'narration.mood.umaga': { tl: 'Umaga', en: 'Morning' },
  'narration.hint': { tl: 'Payo', en: 'Hint' },
  'voice.region': { tl: 'Boses', en: 'Voice' },
  'voice.status.off': { tl: 'Naka-off ang mic', en: 'Mic off' },
  'voice.status.connecting': { tl: 'Kumokonekta ang mic', en: 'Connecting mic' },
  'voice.status.listening': { tl: 'Nakikinig', en: 'Listening' },
  'voice.status.down': { tl: 'Hindi gumagana ang mic', en: 'Voice down' },
  'voice.mode.open': { tl: 'Bukas na mic', en: 'Open mic' },
  'voice.mode.ptt': { tl: 'Pindot para magsalita', en: 'Push to talk' },
  'voice.mode.label': { tl: 'Paraan ng mic', en: 'Mic mode' },
  'voice.problems': { tl: 'Problema sa boses', en: 'Voice problems' },
  'voice.down_banner': {
    tl: 'Hindi gumagana ang boses ngayon. Pwede pa ring mag-tap.',
    en: 'Voice is down. Tap controls still work.'
  },
  'voice.ptt_hold': {
    tl: 'Pindutin at hawakan para magsalita (Space)',
    en: 'Hold to talk (Space)'
  },
  'voice.ptt_held': { tl: 'Nakikinig... (Space)', en: 'Listening... (Space)' },
  'voice.chip_mic': { tl: 'Mic', en: 'Mic' },
  'voice.caption_label': { tl: 'Live na caption', en: 'Live caption' },
  'claim.voice_hint': {
    tl: 'Sabihin: ako si [pangalan], hawak ko ang [piyesa]',
    en: "Say: I'm [name], I'll take [piece]"
  },
  'effect.done': { tl: 'Tapos na', en: 'Done' },
  'effect.seconds': { tl: '[seconds] segundo', en: '[seconds] seconds' },
  'effect.title': { tl: 'Galaw sa mesa', en: 'Table move' },
  'effect.slide_here': { tl: 'Dito', en: 'Here' },
  'effect.remove': { tl: 'Alisin', en: 'Remove' },
  'effect.put_back': { tl: 'Ibalik dito', en: 'Put back here' },
  'status.out': { tl: 'Labas [turns]', en: 'Out [turns]' },
  'status.stolen': { tl: 'Ninakaw', en: 'Stolen' },
  'effect.thrown_float': { tl: 'Itinapon!', en: 'Thrown!' },
  'effect.escape_float': { tl: 'Nakatakas!', en: 'Escaped!' },
  'status.lost': { tl: 'Nawala', en: 'Lost' },
  'lang.title': { tl: 'Wika', en: 'Language' },
  'lang.tl': { tl: 'Filipino', en: 'Filipino' },
  'lang.en': { tl: 'English', en: 'English' },
  'title.sub': { tl: 'Hanggang Umaga', en: 'Until Sunrise' },
  'start.tip': { tl: 'Linisin muna ang mesa.', en: 'Clear the table first.' },
  'start.saves': { tl: 'Mga Baryo', en: 'Your Barrios' },
  'start.placeholder': { tl: 'Hal. San Roque', en: 'e.g. San Roque' },
  'key.title': { tl: 'Ikabit ang AI', en: 'Connect the AI' },
  'key.short_privacy': { tl: 'Naka-encrypt sa laptop na ito.', en: 'Encrypted on this laptop.' },
  'key.offline_short': { tl: 'Maglaro offline', en: 'Play offline' },
  'calib.step_place': { tl: 'Papel na A4 sa gitna', en: 'A4 sheet in the middle' },
  'calib.step_tap': { tl: 'I-tap ang 4 na kanto', en: 'Tap its 4 corners' },
  'calib.step_remove': { tl: 'Alisin ang papel', en: 'Remove the sheet' },
  'calib.area': { tl: 'Laki ng mesa', en: 'Table size' },
  'calib.title': { tl: 'Ayusin ang Camera', en: 'Set Up the Camera' },
  'sfx.on': { tl: 'Tunog: naka-on', en: 'Sound: on' },
  'sfx.off': { tl: 'Tunog: naka-off', en: 'Sound: off' },
  'tut.telegraph': {
    tl: 'Pulang arrow = ang tatamaan nila ngayong turn.',
    en: 'Red arrows show who they will hit this turn.'
  },
  'tut.move': {
    tl: 'Ilipat ang tunay na gamit. Berdeng ring = abot.',
    en: 'Move a real object. Green ring = in reach.'
  },
  'tut.order': {
    tl: 'Sabihin: "Stapler, atake ang aswang!" O i-tap.',
    en: 'Say "Stapler, atake ang aswang!" or tap.'
  },
  'tut.order_tap': {
    tl: 'I-tap ang unit, pili ng aksyon, tapos target.',
    en: 'Tap a unit, pick an action, then a target.'
  },
  'tut.end_turn': {
    tl: 'Handa na? Sabihin ang "Tapos na" o pindutin ang TAPOS.',
    en: 'Ready? Say "Tapos na" or press End turn.'
  },
  'tut.push': {
    tl: 'Itutulak ng tikbalang ang unit. Ilipat sa anino.',
    en: 'A tikbalang shoves a unit. Slide it to the shadow.'
  },
  'tut.dismiss': { tl: 'Sige', en: 'Got it' },
  'tut.skip_all': { tl: 'Laktawan lahat', en: 'Skip all hints' }
} as const satisfies Record<string, CopyEntry>

export type CopyKey = keyof typeof entries

export const copyKeys = Object.keys(entries) as readonly CopyKey[]

export function isCopyKey(key: string): key is CopyKey {
  return Object.prototype.hasOwnProperty.call(entries, key)
}

function fill(text: string, params: CopyParams): string {
  return text.replace(/\[([A-Za-z_]+)\]/g, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match
  )
}

export function t(key: CopyKey, params: CopyParams = {}): CopyEntry {
  const entry: CopyEntry = entries[key]
  return { tl: fill(entry.tl, params), en: fill(entry.en, params) }
}

export function say(key: CopyKey, params: CopyParams = {}): string {
  return t(key, params)[currentLang()]
}

export function pick(entry: Readonly<{ tl: string; en: string }>): string {
  return entry[currentLang()]
}
