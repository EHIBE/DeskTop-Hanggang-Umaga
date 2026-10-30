import NightScene from '../components/NightScene'
import ReplayPanel from '../components/ReplayPanel'
import PixelIcon from '../components/PixelIcon'
import ScorePanel from '../components/ScorePanel'
import Narration from '../hud/Narration'
import { say } from '../lib/copy'
import { palette } from '../lib/palette'
import type { ClientMessage, NarrationMessage, StateMessage } from '../lib/types'

type DefeatProps = Readonly<{
  state: StateMessage
  send: (message: ClientMessage) => boolean
  narration: NarrationMessage | null
}>

function FallenKubo(): React.JSX.Element {
  return (
    <svg
      width="192"
      height="128"
      viewBox="0 0 24 16"
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      <rect x="2" y="14" width="20" height="2" fill={palette.dusk} />
      <rect x="3" y="9" width="6" height="5" fill={palette.nipa} />
      <rect x="9" y="11" width="9" height="3" fill={palette.nipa} />
      <rect x="2" y="7" width="8" height="2" fill={palette.buhangin} />
      <rect x="10" y="9" width="5" height="2" fill={palette.buhangin} />
      <rect x="17" y="8" width="2" height="6" fill={palette.nipa} />
      <rect x="19" y="5" width="1" height="9" fill={palette.sindak} />
      <rect x="20" y="5" width="2" height="2" fill={palette.sindak} />
    </svg>
  )
}

function Defeat({ state, send, narration }: DefeatProps): React.JSX.Element {
  return (
    <main className="relative h-full w-full">
      <NightScene dim />
      <div className="absolute left-[160px] top-[112px] flex w-[880px] flex-col gap-10">
        <div className="rise-in flex items-end gap-10">
          <FallenKubo />
          <h1 className="text-[56px] leading-[64px] text-gabi-sindak [text-shadow:4px_4px_0_var(--color-gabi-ink)]">
            {say('defeat.title')}
          </h1>
        </div>
        <p className="rise-in text-[24px] leading-[40px]" role="status" aria-live="polite">
          {say('lose')}
        </p>
        <Narration
          narration={narration !== null && narration.phase === 'defeat' ? narration : null}
        />
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
            <PixelIcon name="play" size={4} />
            {say('defeat.retry')}
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
      <div
        className="rise-in absolute right-[160px] top-[112px]"
        style={{ animationDelay: '200ms' }}
      >
        <ScorePanel score={state.score} />
      </div>
    </main>
  )
}

export default Defeat
