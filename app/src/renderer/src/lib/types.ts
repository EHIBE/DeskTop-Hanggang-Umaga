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

export type ServerMessage =
  StateMessage | DevicesMessage | CampaignsMessage | FrameMessage | NoticeMessage

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
  | Readonly<{ type: 'demo_safe'; on: boolean }>

export type DesktopConfig = Readonly<{ port: number; token: string }>

export type KeyStatus = 'stored' | 'missing'
