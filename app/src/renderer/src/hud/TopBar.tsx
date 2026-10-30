import { pick, say, t, type CopyKey } from '../lib/copy'
import RecIndicator from './RecIndicator'
import type { AppPhase, NightSummary } from '../lib/types'

type TopBarProps = Readonly<{
  night: NightSummary
  phase: AppPhase
  demoSafe: boolean
  hitCount: number
  recording: boolean
}>

function phaseKey(phase: AppPhase): CopyKey {
  switch (phase) {
    case 'SPAWN_TELEGRAPH':
      return 'phase.spawn'
    case 'PLAYER_PHASE':
      return 'phase.player'
    case 'END_TURN_SNAPSHOT':
    case 'VALIDATE':
      return 'phase.check'
    case 'PAUSED':
      return 'phase.paused'
    default:
      return 'phase.battle'
  }
}

function TopBar({ night, phase, demoSafe, hitCount, recording }: TopBarProps): React.JSX.Element {
  const turn = t('hud.turn', { n: night.turn })
  const banner = t(phaseKey(phase))
  const max = Math.max(1, night.kubo_hp_max)
  const hp = Math.max(0, Math.min(night.kubo_hp, max))
  const kubo = t('hud.kubo')

  return (
    <header className="flex h-[88px] shrink-0 items-center gap-8 border-b-2 border-gabi-dusk bg-gabi-night px-8">
      <div className="flex w-[320px] flex-col text-[24px] leading-[32px]">
        <span>{pick(turn)}</span>
        {recording && <RecIndicator />}
      </div>
      <div
        className="panel flex min-w-0 flex-1 flex-col items-center px-6 py-1"
        role="status"
        aria-live="polite"
        aria-label={pick(banner)}
      >
        <span className="text-[24px] leading-[32px] text-gabi-lantern">{pick(banner)}</span>
      </div>
      <div className="flex w-[560px] items-center justify-end gap-4">
        {demoSafe && <div className="panel px-4 py-2">{say('start.demo_safe')}</div>}
        <span>{pick(kubo)}</span>
        <div
          key={hitCount}
          className={`relative h-[32px] w-[240px] border-2 border-gabi-ink bg-gabi-ink ${
            hitCount > 0 ? 'kubo-hit' : ''
          }`}
          role="meter"
          aria-label={pick(kubo)}
          aria-valuemin={0}
          aria-valuemax={max}
          aria-valuenow={hp}
          aria-valuetext={`${hp}/${max}`}
        >
          <div
            className="absolute left-0 top-0 h-full bg-gabi-lantern"
            style={{ width: `${(hp / max) * 100}%` }}
          />
        </div>
        <span className="w-[112px] text-right text-[24px] leading-[32px]">
          {hp}/{max}
        </span>
      </div>
    </header>
  )
}

export default TopBar
