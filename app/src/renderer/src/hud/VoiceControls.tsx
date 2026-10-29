import { useCallback, useEffect, useRef, useState } from 'react'
import { t } from '../lib/copy'
import type { ClientMessage, VoiceMode, VoiceState, VoiceStatus } from '../lib/types'

type VoiceControlsProps = Readonly<{
  voice: VoiceState
  send: (message: ClientMessage) => boolean
}>

const STATUS_KEY = {
  off: 'voice.status.off',
  connecting: 'voice.status.connecting',
  listening: 'voice.status.listening',
  down: 'voice.status.down'
} as const

const STATUS_GLYPH: Readonly<Record<VoiceStatus, string>> = {
  off: '○',
  connecting: '◐',
  listening: '●',
  down: '▲'
}

const STATUS_TEXT: Readonly<Record<VoiceStatus, string>> = {
  off: 'text-gabi-mist',
  connecting: 'text-gabi-lantern',
  listening: 'text-gabi-dahon',
  down: 'text-gabi-sindak'
}

const MODES: readonly VoiceMode[] = ['open', 'ptt']

function isTextTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

function VoiceControls({ voice, send }: VoiceControlsProps): React.JSX.Element {
  const status: VoiceStatus = voice.status
  const mode: VoiceMode = voice.mode
  const [held, setHeld] = useState(false)
  const heldRef = useRef(false)
  const sendRef = useRef(send)

  useEffect(() => {
    sendRef.current = send
  })

  const setDown = useCallback((down: boolean): void => {
    if (heldRef.current === down) return
    heldRef.current = down
    setHeld(down)
    sendRef.current({ type: 'ptt', down })
  }, [])

  const ptt = mode === 'ptt'

  useEffect(() => {
    if (!ptt) return
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.code !== 'Space' || isTextTarget(event.target)) return
      event.preventDefault()
      if (event.repeat) return
      setDown(true)
    }
    const onKeyUp = (event: KeyboardEvent): void => {
      if (event.code !== 'Space') return
      if (!heldRef.current && isTextTarget(event.target)) return
      event.preventDefault()
      setDown(false)
    }
    const onBlur = (): void => setDown(false)
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    window.addEventListener('blur', onBlur)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      window.removeEventListener('blur', onBlur)
      setDown(false)
    }
  }, [ptt, setDown])

  const showRetry = status !== 'connecting'
  const active = held || (ptt && voice.ptt_down)
  const statusText = t(STATUS_KEY[status])

  return (
    <section aria-label={t('voice.region').en} className="flex shrink-0 items-center gap-3">
      <span
        role="status"
        className={`flex min-h-[48px] items-center gap-2 border-2 border-gabi-dusk bg-gabi-night px-3 ${STATUS_TEXT[status]}`}
        title={statusText.en}
      >
        <span aria-hidden="true">{STATUS_GLYPH[status]}</span>
        <span>{statusText.tl}</span>
        <span className="text-gabi-mist">{t('model.voice').en}</span>
      </span>
      <div role="group" aria-label={t('voice.mode.label').en} className="flex gap-2">
        {MODES.map((candidate) => {
          const label = t(candidate === 'open' ? 'voice.mode.open' : 'voice.mode.ptt')
          return (
            <button
              key={candidate}
              type="button"
              className="btn"
              aria-pressed={mode === candidate}
              title={label.en}
              onClick={() => send({ type: 'voice.mode', mode: candidate })}
            >
              {mode === candidate ? '✓ ' : ''}
              {label.tl}
            </button>
          )
        })}
      </div>
      {ptt && (
        <button
          type="button"
          className={`btn ${active ? 'btn-primary' : ''}`}
          aria-pressed={active}
          title={t('voice.ptt_hold').en}
          onPointerDown={() => setDown(true)}
          onPointerUp={() => setDown(false)}
          onPointerLeave={() => setDown(false)}
          onPointerCancel={() => setDown(false)}
          onContextMenu={(event) => event.preventDefault()}
        >
          {active ? '● ' : '○ '}
          {t(active ? 'voice.ptt_held' : 'voice.ptt_hold').tl}
        </button>
      )}
      {showRetry && (
        <button type="button" className="btn" onClick={() => send({ type: 'voice.retry' })}>
          {t('voice.problems').tl}
        </button>
      )}
    </section>
  )
}

export default VoiceControls
