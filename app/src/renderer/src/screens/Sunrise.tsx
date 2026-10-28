import { useEffect, useState } from 'react'
import Bilingual from '../components/Bilingual'
import ScorePanel from '../components/ScorePanel'
import { t } from '../lib/copy'
import type { ClientMessage, StateMessage } from '../lib/types'

type SunriseProps = Readonly<{
  state: StateMessage
  send: (message: ClientMessage) => boolean
}>

const DAWN_MS = 3000

function Sunrise({ state, send }: SunriseProps): React.JSX.Element {
  const [dawn, setDawn] = useState(false)

  useEffect(() => {
    const frame = requestAnimationFrame(() => setDawn(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  const sky = dawn ? 'var(--color-gabi-bukang)' : 'var(--color-gabi-night)'
  const ground = dawn ? 'var(--color-gabi-liwayway)' : 'var(--color-gabi-ink)'
  const transition = `background-color ${DAWN_MS}ms linear`

  return (
    <main className="relative flex h-full w-full flex-col items-center">
      <div
        className="absolute inset-0"
        style={{ backgroundColor: sky, transition }}
        aria-hidden="true"
      />
      <div
        className="absolute bottom-0 left-0 h-[320px] w-full"
        style={{ backgroundColor: ground, transition }}
        aria-hidden="true"
      />
      <div className="relative z-10 flex h-full w-full flex-col items-center gap-8 pt-16">
        <h1 className="text-[48px] leading-[56px] text-gabi-ink">{t('sunrise.title').tl}</h1>
        <p className="text-gabi-night">{t('sunrise.title').en}</p>
        <div className="panel w-[880px] p-4 text-center" role="status" aria-live="polite">
          <Bilingual copyKey="win" />
        </div>
        <ScorePanel score={state.score} />
        <div className="flex gap-6">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => send({ type: 'night.next' })}
          >
            {t('sunrise.next').tl}
          </button>
          <button type="button" className="btn" onClick={() => send({ type: 'night.quit' })}>
            {t('sunrise.quit').tl}
          </button>
        </div>
      </div>
    </main>
  )
}

export default Sunrise
