import { t } from '../lib/copy'
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
    <section className="panel flex w-[720px] flex-col gap-4 p-6 text-gabi-moon">
      {rows.map(([key, value]) => (
        <div key={key} className="flex items-baseline justify-between gap-4">
          <span>
            {t(key).tl}
            <span className="caption-en block">{t(key).en}</span>
          </span>
          <span className="text-[24px] leading-[32px]">{value}</span>
        </div>
      ))}
      {score && (
        <div className="flex items-baseline justify-between gap-4 border-t-2 border-gabi-dusk pt-4">
          <span className="text-gabi-lantern">
            {t('score.total').tl}
            <span className="caption-en block">{t('score.total').en}</span>
          </span>
          <span className="text-[48px] leading-[56px] text-gabi-lantern">{score.score}</span>
        </div>
      )}
      <div className="flex flex-col gap-2 border-t-2 border-gabi-dusk pt-4">
        <span>
          {t('score.bayani').tl}
          <span className="caption-en block">{t('score.bayani').en}</span>
        </span>
        <span className="text-gabi-lantern">
          {score && score.bayani.length > 0 ? score.bayani.join(', ') : t('score.bayani_none').tl}
        </span>
      </div>
    </section>
  )
}

export default ScorePanel
