export type Difficulty = 'madali' | 'normal' | 'mahirap'

export type AppPhase = 'START' | 'CALIBRATE' | 'SUMMON'

export type FrameView = 'raw' | 'warped'

export type CopyParams = Readonly<Record<string, string | number>>

export type CampaignSummary = Readonly<{
  id: string
  name: string
  difficulty: Difficulty
  nights_survived: number
  created_at: string
}>

export type CameraInfo = Readonly<{ index: number; width: number; height: number }>

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
}>

export type Pose = Readonly<{ id: string; x_cm: number; y_cm: number; uncertain: boolean }>

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
  has_api_key: boolean
  units: readonly UnitSummary[]
  begin_block_key: string | null
  awaiting_tap: boolean
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

export type CardMessage = Readonly<{ type: 'card'; seq: number; unit: UnitSummary }>

export type ServerMessage =
  StateMessage | DevicesMessage | CampaignsMessage | FrameMessage | NoticeMessage | CardMessage

export type CampaignStartMessage =
  | Readonly<{ type: 'campaign.start'; campaign_id: string }>
  | Readonly<{ type: 'campaign.start'; new: Readonly<{ name: string; difficulty: Difficulty }> }>

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
  | Readonly<{ type: 'demo_safe'; on: boolean }>

export type DesktopConfig = Readonly<{ port: number; token: string }>

export type KeyStatus = 'stored' | 'missing'
