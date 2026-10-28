import Bilingual from '../components/Bilingual'
import ScorePanel from '../components/ScorePanel'
import Narration from '../hud/Narration'
import { t } from '../lib/copy'
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
    <main className="flex h-full w-full flex-col items-center gap-8 bg-gabi-ink pt-16">
      <h1 className="text-[48px] leading-[56px] text-gabi-sindak">{t('defeat.title').tl}</h1>
      <p className="caption-en">{t('defeat.title').en}</p>
      <FallenKubo />
      <div className="panel w-[880px] p-4 text-center" role="status" aria-live="polite">
        <Bilingual copyKey="lose" />
      </div>
      <Narration
        narration={narration !== null && narration.phase === 'defeat' ? narration : null}
        className="w-[1200px]"
      />
      <ScorePanel score={state.score} />
      <div className="flex gap-6">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => send({ type: 'night.next' })}
        >
          {t('defeat.retry').tl}
        </button>
        <button type="button" className="btn" onClick={() => send({ type: 'night.quit' })}>
          {t('sunrise.quit').tl}
        </button>
      </div>
    </main>
  )
}

export default Defeat
