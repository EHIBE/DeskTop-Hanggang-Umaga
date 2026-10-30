import { say } from '../lib/copy'
import type { ScoreSummary } from '../lib/types'

type ScorePanelProps = Readonly<{ score: ScoreSummary | null }>

function ScorePanel({ score }: ScorePanelProps): React.JSX.Element {
  const rows = score
    ? ([
        ['score.alive', score.units_alive],
        ['score.kubo', score.kubo_hp],
        ['score.defeated', score.enemies_defeated]
      ] as const)
    : []

  return (
    <section className="window flex w-[640px] flex-col gap-4 p-10 text-gabi-moon">
      {rows.map(([key, value]) => (
        <div key={key} className="flex items-baseline justify-between gap-4">
          <span className="text-gabi-mist">{say(key)}</span>
          <span className="text-[24px] leading-[32px]">{value}</span>
        </div>
      ))}
      {score && (
        <div className="flex items-baseline justify-between gap-4 border-t-2 border-gabi-dusk pt-4">
          <span className="text-gabi-lantern">{say('score.total')}</span>
          <span className="title-mark text-[56px] leading-[64px]">{score.score}</span>
        </div>
      )}
      <div className="flex flex-col gap-2 border-t-2 border-gabi-dusk pt-4">
        <span className="text-gabi-mist">{say('score.bayani')}</span>
        <span className="text-[24px] leading-[32px] text-gabi-lantern">
          {score && score.bayani.length > 0 ? score.bayani.join(', ') : say('score.bayani_none')}
        </span>
      </div>
    </section>
  )
}

export default ScorePanel
