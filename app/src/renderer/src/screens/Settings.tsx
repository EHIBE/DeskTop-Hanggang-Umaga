import { useEffect, useState } from 'react'
import Dialog from '../components/Dialog'
import PixelIcon from '../components/PixelIcon'
import { say, type CopyKey } from '../lib/copy'
import { setLang, useLang, type Lang } from '../lib/lang'
import type { MessageHandler } from '../lib/socket'
import type {
  CameraInfo,
  ClientMessage,
  MicrophoneInfo,
  SettingsDifficulty,
  SettingsValues,
  StateMessage
} from '../lib/types'

type SettingsProps = Readonly<{
  state: StateMessage
  send: (message: ClientMessage) => boolean
  subscribe: (handler: MessageHandler) => () => void
  onBack: () => void
}>

type RowProps = Readonly<{
  id: string
  label: string
  hint?: string
  children: React.ReactNode
}>

type SwitchKey = 'replay_enabled' | 'show_real_objects' | 'strict_ownership' | 'generated_map'

type SwitchRow = Readonly<{ key: SwitchKey; label: CopyKey; hint: CopyKey | null }>

const TITLE_ID = 'settings-title'

const LEVELS: readonly Readonly<{ value: SettingsDifficulty; label: CopyKey }>[] = [
  { value: 'easy', label: 'diff.madali' },
  { value: 'normal', label: 'diff.normal' },
  { value: 'hard', label: 'diff.mahirap' }
]

const LANGS: readonly Readonly<{ value: Lang; label: CopyKey }>[] = [
  { value: 'tl', label: 'lang.tl' },
  { value: 'en', label: 'lang.en' }
]

const FIRST_SWITCHES: readonly SwitchRow[] = [
  { key: 'replay_enabled', label: 'settings.replay', hint: 'settings.replay_hint' }
]

const LAST_SWITCHES: readonly SwitchRow[] = [
  { key: 'show_real_objects', label: 'settings.real', hint: 'settings.real_hint' },
  { key: 'strict_ownership', label: 'settings.strict', hint: 'settings.strict_hint' },
  { key: 'generated_map', label: 'settings.map', hint: 'settings.map_hint' }
]

function Row({ id, label, hint, children }: RowProps): React.JSX.Element {
  return (
    <div role="group" aria-labelledby={id} className="flex items-start gap-8 py-4">
      <div className="flex w-[480px] shrink-0 flex-col gap-1">
        <span id={id} className="text-gabi-moon">
          {label}
        </span>
        {hint !== undefined && <span className="caption-en">{hint}</span>}
      </div>
      <div className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-3">{children}</div>
    </div>
  )
}

function Switch({
  labelledBy,
  on,
  disabled = false,
  onChange
}: Readonly<{
  labelledBy: string
  on: boolean
  disabled?: boolean
  onChange: (next: boolean) => void
}>): React.JSX.Element {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-labelledby={labelledBy}
      disabled={disabled}
      className="btn w-[200px]"
      onClick={() => onChange(!on)}
    >
      <PixelIcon name={on ? 'check' : 'cross'} size={3} className={on ? 'text-gabi-dahon' : ''} />
      {say(on ? 'settings.on' : 'settings.off')}
    </button>
  )
}

function Settings({ state, send, subscribe, onBack }: SettingsProps): React.JSX.Element {
  const values: SettingsValues = state.settings
  const lang = useLang()
  const inNight = state.phase !== 'START'
  const [cameras, setCameras] = useState<readonly CameraInfo[]>([])
  const [microphones, setMicrophones] = useState<readonly MicrophoneInfo[]>([])

  useEffect(() => {
    const off = subscribe((message) => {
      if (message.type === 'devices') {
        setCameras(message.cameras)
        setMicrophones(message.microphones)
      }
    })
    send({ type: 'settings.get' })
    if (!inNight) send({ type: 'devices.list' })
    return off
  }, [subscribe, send, inNight])

  const set = (key: keyof SettingsValues, value: boolean | number | string): void => {
    send({ type: 'settings.set', key, value })
  }

  const cameraIndexes =
    cameras.length > 0 ? cameras.map((camera) => camera.index) : [values.camera_device]
  const micChoices = [
    { id: 'default', label: say('settings.mic_default') },
    ...microphones.map((mic) => ({ id: String(mic.index), label: mic.name }))
  ]
  if (!micChoices.some((choice) => choice.id === values.mic_device)) {
    micChoices.push({ id: values.mic_device, label: values.mic_device })
  }

  const renderSwitches = (rows: readonly SwitchRow[]): React.JSX.Element[] =>
    rows.map((row) => (
      <Row
        key={row.key}
        id={`setting-${row.key}`}
        label={say(row.label)}
        hint={row.hint === null ? undefined : say(row.hint)}
      >
        <Switch
          labelledBy={`setting-${row.key}`}
          on={values[row.key]}
          onChange={(next) => set(row.key, next)}
        />
      </Row>
    ))

  return (
    <Dialog
      titleId={TITLE_ID}
      onEscape={onBack}
      className="flex max-h-[960px] w-[1400px] flex-col gap-4 p-10"
    >
      <h2
        id={TITLE_ID}
        className="flex items-center gap-4 text-[24px] leading-[32px] text-gabi-lantern"
      >
        <PixelIcon name="gear" size={4} />
        {say('settings.title')}
      </h2>
      <div className="-mx-4 flex min-h-0 flex-col divide-y-2 divide-gabi-dusk overflow-y-auto px-4">
        <Row
          id="setting-camera"
          label={say('settings.camera')}
          hint={inNight ? say('settings.camera_locked') : undefined}
        >
          {cameraIndexes.map((index) => (
            <button
              key={index}
              type="button"
              className="btn"
              aria-pressed={values.camera_device === index}
              disabled={inNight}
              onClick={() => set('camera_device', index)}
            >
              {index + 1}
            </button>
          ))}
        </Row>
        <Row id="setting-mic" label={say('settings.mic')}>
          {micChoices.map((choice) => (
            <button
              key={choice.id}
              type="button"
              className="btn max-w-[360px]"
              aria-pressed={values.mic_device === choice.id}
              onClick={() => set('mic_device', choice.id)}
            >
              <span className="truncate">{choice.label}</span>
            </button>
          ))}
        </Row>
        <Row id="setting-captions" label={say('settings.captions')}>
          <div role="radiogroup" aria-labelledby="setting-captions" className="segmented w-[480px]">
            {LANGS.map((option) => (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={lang === option.value}
                onClick={() => setLang(option.value)}
              >
                {say(option.label)}
              </button>
            ))}
          </div>
        </Row>
        <Row id="setting-difficulty" label={say('settings.difficulty')}>
          <div
            role="radiogroup"
            aria-labelledby="setting-difficulty"
            className="segmented w-[640px]"
          >
            {LEVELS.map((option) => (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={values.difficulty === option.value}
                onClick={() => set('difficulty', option.value)}
              >
                {say(option.label)}
              </button>
            ))}
          </div>
        </Row>
        {renderSwitches(FIRST_SWITCHES)}
        <Row
          id="setting-tts"
          label={say('settings.tts')}
          hint={state.tts_available ? undefined : say('settings.tts_unavailable')}
        >
          <Switch
            labelledBy="setting-tts"
            on={values.tts_enabled && state.tts_available}
            disabled={!state.tts_available}
            onChange={(next) => set('tts_enabled', next)}
          />
        </Row>
        {renderSwitches(LAST_SWITCHES)}
      </div>
      <button type="button" className="btn shrink-0 self-end" onClick={onBack}>
        {say('nav.back')}
      </button>
    </Dialog>
  )
}

export default Settings
