import { useEffect, useState } from 'react'
import BadgePanel from '../components/BadgePanel'
import PixelIcon from '../components/PixelIcon'
import ReplayPanel from '../components/ReplayPanel'
import ScorePanel from '../components/ScorePanel'
import MomentLine from '../hud/MomentLine'
import Narration from '../hud/Narration'
import { say } from '../lib/copy'
import type { ClientMessage, MomentMessage, NarrationMessage, StateMessage } from '../lib/types'

type SunriseProps = Readonly<{
  state: StateMessage
  send: (message: ClientMessage) => boolean
  narration: NarrationMessage | null
  moment: MomentMessage | null
}>

const DAWN_MS = 3000

function Sunrise({ state, send, narration, moment }: SunriseProps): React.JSX.Element {
  const [dawn, setDawn] = useState(false)

  useEffect(() => {
    const frame = requestAnimationFrame(() => setDawn(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  const transition = `background-color ${DAWN_MS}ms steps(6)`
  const bands = [
    dawn ? 'var(--color-gabi-liwayway)' : 'var(--color-gabi-ink)',
    dawn ? 'var(--color-gabi-bukang)' : 'var(--color-gabi-night)',
    dawn ? 'var(--color-gabi-buhangin)' : 'var(--color-gabi-dusk)'
  ]

  return (
    <main className="relative h-full w-full overflow-hidden">
      <div className="absolute inset-0 flex flex-col" aria-hidden="true">
        <div className="flex-[5]" style={{ backgroundColor: bands[0], transition }} />
        <div className="flex-[3]" style={{ backgroundColor: bands[1], transition }} />
        <div className="flex-[2]" style={{ backgroundColor: bands[2], transition }} />
      </div>
      <div
        className="absolute right-[520px] text-gabi-lantern"
        style={{
          bottom: dawn ? 760 : 40,
          transition: `bottom ${DAWN_MS}ms cubic-bezier(0.16, 1, 0.3, 1)`
        }}
        aria-hidden="true"
      >
        <PixelIcon name="sun" size={32} />
      </div>
      <div className="absolute bottom-0 left-0 h-[96px] w-full bg-gabi-nipa" aria-hidden="true" />
      <div className="absolute left-[160px] top-[112px] flex w-[880px] flex-col gap-10">
        <h1 className="rise-in title-mark text-[72px] leading-[80px]">{say('sunrise.title')}</h1>
        <p
          className="rise-in text-[24px] leading-[40px] text-gabi-ink"
          role="status"
          aria-live="polite"
        >
          {say('win')}
        </p>
        {state.progression !== null && (
          <p className="rise-in flex flex-wrap items-center gap-x-6 gap-y-2 text-gabi-ink">
            <span className="flex items-center gap-3">
              <PixelIcon name="sun" size={3} />
              {say('progress.level', { n: state.progression.barrio_level })}
            </span>
            <span className="flex items-center gap-3">
              <PixelIcon name="moon" size={3} />
              {say('start.nights', { n: state.progression.nights_survived })}
            </span>
          </p>
        )}
        <Narration
          narration={narration !== null && narration.phase === 'sunrise' ? narration : null}
        />
        <MomentLine moment={moment} />
        <ReplayPanel
          replay={state.replay}
          hadPlayers={(state.night?.players.length ?? 0) > 0}
          send={send}
        />
        <div className="flex gap-6">
          <button
            type="button"
            className="btn btn-primary btn-big text-[24px]"
            onClick={() => send({ type: 'night.next' })}
          >
            <PixelIcon name="moon" size={4} />
            {say('sunrise.next')}
          </button>
          <button
            type="button"
            className="btn btn-big"
            onClick={() => send({ type: 'night.quit' })}
          >
            {say('sunrise.quit')}
          </button>
        </div>
      </div>
      {state.progression !== null && (
        <div className="rise-in absolute right-[160px] top-[72px]">
          <BadgePanel progression={state.progression} units={state.units} send={send} />
        </div>
      )}
      <div
        className="rise-in absolute right-[160px] top-[400px]"
        style={{ animationDelay: '200ms' }}
      >
        <ScorePanel score={state.score} />
      </div>
    </main>
  )
}

export default Sunrise
