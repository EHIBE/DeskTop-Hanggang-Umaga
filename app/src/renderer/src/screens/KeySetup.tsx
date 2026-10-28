import { useState } from 'react'
import Bilingual from '../components/Bilingual'
import { t } from '../lib/copy'
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
    <main className="flex h-full w-full items-center justify-center">
      <form
        className="panel flex w-[960px] flex-col gap-6 p-8"
        onSubmit={(event) => {
          event.preventDefault()
          void save()
        }}
      >
        <Bilingual copyKey="key.prompt" />
        <label htmlFor="api-key" className="caption-tl">
          {t('key.label').tl}
        </label>
        <input
          id="api-key"
          type="password"
          autoComplete="off"
          spellCheck={false}
          className="field w-full"
          value={value}
          aria-invalid={phase === 'invalid'}
          aria-describedby="key-status"
          onChange={(event) => {
            setValue(event.target.value)
            if (phase !== 'saving') setPhase('idle')
          }}
        />
        <div id="key-status" role="status" aria-live="polite">
          {phase === 'invalid' && (
            <div className="banner banner-error p-4">
              <Bilingual copyKey="key.invalid" />
            </div>
          )}
          {phase === 'saved' && (
            <div className="banner p-4">
              <Bilingual copyKey="key.saved" />
            </div>
          )}
        </div>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={phase === 'saving' || value.trim().length === 0}
        >
          {t('key.save').tl}
        </button>
        <Bilingual copyKey="key.privacy" />
        <button type="button" className="btn" onClick={goOffline}>
          {t('key.offline').tl}
          <span className="caption-en block">{t('key.offline').en}</span>
        </button>
      </form>
    </main>
  )
}

export default KeySetup
