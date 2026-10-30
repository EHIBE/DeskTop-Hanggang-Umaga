import { useState } from 'react'
import LangToggle from '../components/LangToggle'
import NightScene from '../components/NightScene'
import PixelIcon from '../components/PixelIcon'
import TitleMark from '../components/TitleMark'
import { say } from '../lib/copy'
import type { ClientMessage, KeyStatus } from '../lib/types'

type KeySetupProps = Readonly<{
  send: (message: ClientMessage) => boolean
  onKeyStatus: (status: KeyStatus) => void
  onContinueOffline: () => void
}>

type Phase = 'idle' | 'saving' | 'saved' | 'invalid'

function KeySetup({ send, onKeyStatus, onContinueOffline }: KeySetupProps): React.JSX.Element {
  const [value, setValue] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')

  const save = async (): Promise<void> => {
    const key = value.trim()
    if (key.length === 0) {
      setPhase('invalid')
      return
    }
    setPhase('saving')
    try {
      const status = await window.desktop.saveKey(key)
      if (status === 'stored') {
        setValue('')
        setPhase('saved')
        onKeyStatus(status)
      } else {
        setPhase('invalid')
      }
    } catch {
      setPhase('invalid')
    }
  }

  const goOffline = (): void => {
    send({ type: 'demo_safe', on: true })
    onContinueOffline()
  }

  return (
    <main className="relative h-full w-full">
      <NightScene />
      <div className="absolute left-[160px] top-[112px] flex w-[720px] flex-col gap-16">
        <div className="rise-in">
          <TitleMark />
        </div>
        <form
          className="window rise-in flex flex-col gap-8 p-10"
          style={{ animationDelay: '120ms' }}
          onSubmit={(event) => {
            event.preventDefault()
            void save()
          }}
        >
          <h2 className="text-[24px] leading-[32px]">{say('key.title')}</h2>
          <div className="flex flex-col gap-3">
            <label htmlFor="api-key" className="label">
              {say('key.label')}
            </label>
            <input
              id="api-key"
              type="password"
              autoComplete="off"
              autoFocus
              spellCheck={false}
              className="field w-full"
              value={value}
              aria-invalid={phase === 'invalid'}
              aria-describedby="key-status key-privacy"
              onChange={(event) => {
                setValue(event.target.value)
                if (phase !== 'saving') setPhase('idle')
              }}
            />
            <p id="key-privacy" className="flex items-center gap-3 text-gabi-mist">
              <PixelIcon name="lock" size={2} />
              {say('key.short_privacy')}
            </p>
          </div>
          <div id="key-status" role="status" aria-live="polite">
            {phase === 'invalid' && (
              <p className="flex items-center gap-3 text-gabi-bukang">
                <PixelIcon name="cross" size={2} />
                {say('key.invalid')}
              </p>
            )}
            {phase === 'saved' && (
              <p className="flex items-center gap-3 text-gabi-dahon">
                <PixelIcon name="check" size={2} />
                {say('key.saved')}
              </p>
            )}
          </div>
          <div className="flex items-center gap-6">
            <button
              type="submit"
              className="btn btn-primary btn-big flex-1 text-[24px]"
              disabled={phase === 'saving' || value.trim().length === 0}
            >
              {phase === 'saving' ? say('summon.busy') : say('key.save')}
            </button>
            <button type="button" className="btn btn-big flex-1" onClick={goOffline}>
              <PixelIcon name="wifi" size={3} />
              {say('key.offline_short')}
            </button>
          </div>
        </form>
      </div>
      <LangToggle className="absolute bottom-[20px] right-[64px]" />
    </main>
  )
}

export default KeySetup
