export type Difficulty = 'madali' | 'normal' | 'mahirap'

export type AppPhase =
  | 'START'
  | 'CALIBRATE'
  | 'SUMMON'
  | 'VOICE_CLAIM'
  | 'SPAWN_TELEGRAPH'
  | 'PLAYER_PHASE'
  | 'END_TURN_SNAPSHOT'
  | 'VALIDATE'
  | 'RESOLVE_PLAYER'
  | 'RESOLVE_ENEMY'
  | 'PHYSICAL_EFFECTS'
  | 'CHECK_END'
  | 'SUNRISE'
  | 'DEFEAT'
  | 'PAUSED'

export type EnemyType = 'aswang' | 'tikbalang' | 'kapre' | 'manananggal' | 'duwende'

export type IntentAction = 'attack' | 'power' | 'heal'

export type EventType =
  | 'attack'
  | 'dodge'
  | 'spawn'
  | 'intent'
  | 'heal'
  | 'power'
  | 'shield'
  | 'down'
  | 'push'
  | 'thrown'
  | 'steal'
  | 'return'
  | 'escape'
  | 'split'
  | 'reform'
  | 'kubo_hit'
  | 'defeat_enemy'
  | 'smoke'
  | 'smoke_cleared'
  | 'lost'
  | 'found'
  | 'win'
  | 'lose'

export type GameEvent = Readonly<{
  type: EventType
  src: string | null
  dst: string | null
  dmg: number | null
  edge: string | null
  pos: Readonly<{ x_cm: number; y_cm: number }> | null
}>

export type EnemySummary = Readonly<{
  id: string
  type: EnemyType
  part: 'upper' | 'lower' | null
  hp: number
  hp_max: number
  x_cm: number
  y_cm: number
  intent: Readonly<{ target_id: string; dmg: number }> | null
  stunned: boolean
}>

export type NightUnit = Readonly<{
  id: string
  hp: number
  hp_max: number
  cooldown: number
  is_down: boolean
  is_move_legal: boolean
  start_x_cm: number
  start_y_cm: number
  move_cm: number
  range_cm: number
  owner: string | null
  status: readonly string[]
  badges: readonly BadgeKind[]
  scars: number
  cooldown_cut: number
  smoked: boolean
}>

export type BadgeKind = 'hp' | 'cooldown'

export type SmokeCloud = Readonly<{
  source_id: string
  x_cm: number
  y_cm: number
  radius_cm: number
}>

export type EffectKind = 'push' | 'steal'

export type NightEffect = Readonly<{
  kind: EffectKind
  unit_id: string
  x_cm: number
  y_cm: number
}>

export type ChipSource = 'tap' | 'voice'

export type Chip = Readonly<{
  chip_id: string
  unit_id: string
  action: IntentAction
  target_id: string | null
  source?: ChipSource
  speaker?: string | null
}>

export type NightSummary = Readonly<{
  number: number
  turn: number
  difficulty: Difficulty
  players: readonly string[]
  units: readonly NightUnit[]
  enemies: readonly EnemySummary[]
  chips: readonly Chip[]
  illegal_units: readonly string[]
  kubo_hp: number
  kubo_hp_max: number
  effects: readonly NightEffect[]
  effect_seconds_left: number
  smoke: readonly SmokeCloud[]
}>

export type ScoreSummary = Readonly<{
  units_alive: number
  kubo_hp: number
  enemies_defeated: number
  score: number
  bayani: readonly string[]
}>

export type FrameView = 'raw' | 'warped'

export type CopyParams = Readonly<Record<string, string | number>>

export type CampaignSummary = Readonly<{
  id: string
  name: string
  difficulty: Difficulty
  nights_survived: number
  created_at: string
}>

export type CameraInfo = Readonly<{
  index: number
  width: number
  height: number
  has_picture: boolean
}>

export type MicrophoneInfo = Readonly<{ index: number; name: string }>

export type Point = readonly [number, number]

export type UnitClass =
  'kubo' | 'charm' | 'healer' | 'fighter' | 'reach' | 'ranged' | 'scout' | 'wall'

export type MoveClass = 'none' | 'short' | 'medium' | 'long'

export type RangeClass = 'none' | 'melee' | 'reach' | 'far'

export type PowerId =
  | 'none'
  | 'P01'
  | 'P02'
  | 'P03'
  | 'P04'
  | 'P05'
  | 'P06'
  | 'P07'
  | 'P08'
  | 'P09'
  | 'P10'
  | 'P11'
  | 'P12'

export type UnitSummary = Readonly<{
  id: string
  unit_id: string
  sam_id: number
  name: string
  class: UnitClass
  hp: number
  hp_max: number
  atk: number
  move: MoveClass
  range: RangeClass
  power_id: PowerId
  power_name_tl: string
  card_text_tl: string
  card_text_en: string
  x_cm: number
  y_cm: number
  rerolls_left: number
  sprite_png: string | null
  returning: boolean
  badges: readonly BadgeKind[]
  scars: number
}>

export type Pose = Readonly<{ id: string; x_cm: number; y_cm: number; uncertain: boolean }>

export type VoiceStatus = 'off' | 'connecting' | 'listening' | 'down'

export type VoiceMode = 'open' | 'ptt'

export type VoiceState = Readonly<{
  status: VoiceStatus
  mode: VoiceMode
  ptt_down: boolean
}>

export type ReplayStatus = 'idle' | 'working' | 'done' | 'failed'

export type ReplayState = Readonly<{
  status: ReplayStatus
  file: string | null
  available: boolean
}>

export type CaptionLanguage = 'tl' | 'en'

export type SettingsDifficulty = 'easy' | 'normal' | 'hard'

export type SettingsValues = Readonly<{
  camera_device: number
  mic_device: string
  caption_language: CaptionLanguage
  difficulty: SettingsDifficulty
  replay_enabled: boolean
  tts_enabled: boolean
  show_real_objects: boolean
  strict_ownership: boolean
  generated_map: boolean
}>

export type SettingKey = keyof SettingsValues

export type BadgeOffer = Readonly<{ unit_id: string; choices: readonly BadgeKind[] }>

export type Progression = Readonly<{
  barrio_level: number
  nights_survived: number
  badge_offers: readonly BadgeOffer[]
}>

export type RecapSource = 'spark' | 'line_bank' | 'glimmer'

export type RecapPayload = Readonly<{
  night: number
  text_tl: string
  text_en: string
  mood: NarrationMood
  source: RecapSource
}>

export type PendingConfirm = Readonly<{
  confirm_id: string
  unit_id: string
  unit_name: string
  owner: string
  speaker: string | null
  action: IntentAction
  target_id: string | null
  text_tl: string
  text_en: string
  seconds_left: number
}>

export type MapState = Readonly<{ enabled: boolean; ready: boolean; working: boolean }>

export type StateMessage = Readonly<{
  type: 'state'
  seq: number
  phase: AppPhase
  campaign: CampaignSummary | null
  camera: CameraInfo | null
  calibrated: boolean
  calibration_preview: boolean
  play_w_cm: number
  play_h_cm: number
  demo_safe: boolean
  demo_safe_sam: boolean
  resume_turn: number | null
  has_api_key: boolean
  units: readonly UnitSummary[]
  begin_block_key: string | null
  awaiting_tap: boolean
  night: NightSummary | null
  score: ScoreSummary | null
  voice: VoiceState
  recording: boolean
  consents: Readonly<Record<string, boolean>>
  replay: ReplayState
  settings: SettingsValues
  tts_available: boolean
  progression: Progression | null
  recap: RecapPayload | null
  pending_confirm: PendingConfirm | null
  map: MapState
}>

export type DevicesMessage = Readonly<{
  type: 'devices'
  seq: number
  cameras: readonly CameraInfo[]
  microphones: readonly MicrophoneInfo[]
}>

export type CampaignsMessage = Readonly<{
  type: 'campaigns'
  seq: number
  campaigns: readonly CampaignSummary[]
}>

export type FrameMessage = Readonly<{
  type: 'frame'
  seq: number
  view: FrameView
  width: number
  height: number
  jpg: string
  poses: readonly Pose[]
}>

export type NoticeMessage = Readonly<{
  type: 'notice'
  seq: number
  copy_key: string
  params: CopyParams
}>

export type SpriteMessage = Readonly<{
  type: 'sprite'
  seq: number
  unit_id: string
  sprite_png: string
}>

export type CostMessage = Readonly<{
  type: 'cost'
  seq: number
  spent_usd: string
  warn: boolean
  stopped: boolean
}>

export type EventsMessage = Readonly<{
  type: 'events'
  seq: number
  turn: number
  events: readonly GameEvent[]
}>

export type NarrationPhase = 'night_start' | 'resolution_then_telegraph' | 'sunrise' | 'defeat'

export type NarrationMood = 'kalmado' | 'kaba' | 'takot' | 'tagumpay' | 'umaga'

export type NarrationCallout = Readonly<{ entity_id: string; text_tl: string }>

export type NarrationMessage = Readonly<{
  type: 'narration'
  night: number
  turn: number
  phase: NarrationPhase
  narration_tl: string
  narration_en: string
  mood: NarrationMood
  callouts: readonly NarrationCallout[]
  hint_tl: string
  source: 'spark' | 'line_bank'
}>

export type CaptionMessage = Readonly<{
  type: 'caption'
  turn_id: string
  text: string
  is_final: boolean
  speaker: string | null
}>

export type CardMessage = Readonly<{ type: 'card'; seq: number; unit: UnitSummary }>

export type SummonSource = 'spark' | 'fallback'

export type SummonResultMessage = Readonly<{
  type: 'summon.result'
  unit_id: string
  game_id: string
  source: SummonSource
  spark_box: readonly [number, number, number, number] | null
  mask_hull: readonly Point[]
  width: number
  height: number
  returning: boolean
}>

export type SettingsMessage = Readonly<{
  type: 'settings'
  seq: number
  values: SettingsValues
  tts_available: boolean
}>

export type MapMessage = Readonly<{ type: 'map'; seq: number; png: string }>

export type CropsMessage = Readonly<{
  type: 'crops'
  seq: number
  crops: Readonly<Record<string, string>>
}>

export type MomentName =
  | 'kapre_smoke_telegraph'
  | 'kapre_smoke_hit'
  | 'unit_lost'
  | 'unit_returned'
  | 'badge_earned'
  | 'scar_gained'
  | 'object_recognized'

export type MomentMessage = Readonly<{
  type: 'moment'
  seq: number
  moment: MomentName
  text_tl: string
  text_en: string
  mood: NarrationMood
  unit_id: string | null
}>

export type RecapMessage = Readonly<RecapPayload & { type: 'recap'; seq: number }>

export type ServerMessage =
  | SettingsMessage
  | MapMessage
  | CropsMessage
  | MomentMessage
  | RecapMessage
  | SummonResultMessage
  | StateMessage
  | DevicesMessage
  | CampaignsMessage
  | FrameMessage
  | NoticeMessage
  | CardMessage
  | SpriteMessage
  | CostMessage
  | EventsMessage
  | NarrationMessage
  | CaptionMessage

export type CampaignStartMessage =
  | Readonly<{ type: 'campaign.start'; campaign_id: string }>
  | Readonly<{
      type: 'campaign.start'
      new: Readonly<{ name: string; difficulty?: Difficulty }>
    }>

export type ClientMessage =
  | Readonly<{ type: 'campaign.list' }>
  | CampaignStartMessage
  | Readonly<{ type: 'devices.list' }>
  | Readonly<{ type: 'camera.select'; index: number }>
  | Readonly<{
      type: 'calibrate.corners'
      corners: readonly [Point, Point, Point, Point]
      play_w_cm: number
      play_h_cm: number
    }>
  | Readonly<{ type: 'calibrate.done' }>
  | Readonly<{ type: 'calibrate.restart' }>
  | Readonly<{ type: 'summon.name'; name: string }>
  | Readonly<{ type: 'summon.tap'; point: Point }>
  | Readonly<{ type: 'unit.reroll'; unit_id: string }>
  | Readonly<{ type: 'unit.rename'; unit_id: string; name: string }>
  | Readonly<{ type: 'night.begin' }>
  | Readonly<{ type: 'claim.tap'; player_name: string; unit_ids: readonly string[] }>
  | Readonly<{ type: 'claim.done' }>
  | Readonly<{ type: 'consent'; player_name: string; agree: boolean }>
  | Readonly<{ type: 'effect.done' }>
  | Readonly<{
      type: 'intent.tap'
      unit_id: string
      action: IntentAction
      target_id: string | null
    }>
  | Readonly<{ type: 'chip.cancel'; chip_id: string }>
  | Readonly<{ type: 'end_turn' }>
  | Readonly<{ type: 'night.next' }>
  | Readonly<{ type: 'night.quit' }>
  | Readonly<{ type: 'demo_safe'; on: boolean }>
  | Readonly<{ type: 'demo_safe.sam'; on: boolean }>
  | Readonly<{ type: 'campaign.delete'; campaign_id: string }>
  | Readonly<{ type: 'night.pause' }>
  | Readonly<{ type: 'night.resume'; force: boolean }>
  | Readonly<{ type: 'ptt'; down: boolean }>
  | Readonly<{ type: 'voice.mode'; mode: VoiceMode }>
  | Readonly<{ type: 'voice.retry' }>
  | Readonly<{ type: 'replay.request' }>
  | Readonly<{ type: 'settings.get' }>
  | Readonly<{ type: 'settings.set'; key: SettingKey; value: boolean | number | string }>
  | Readonly<{ type: 'badge.pick'; unit_id: string; badge: BadgeKind }>
  | Readonly<{ type: 'confirm.accept'; confirm_id: string }>
  | Readonly<{ type: 'confirm.cancel'; confirm_id: string }>
  | Readonly<{ type: 'map.get' }>
  | Readonly<{ type: 'crops.get' }>
  | Readonly<{ type: 'pause.quit' }>
  | Readonly<{ type: 'calibrate.back' }>

export type DesktopConfig = Readonly<{ port: number; token: string }>

export type KeyStatus = 'stored' | 'missing'
