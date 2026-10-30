import { pick, t } from '../lib/copy'
import { palette } from '../lib/palette'
import type { CostMessage } from '../lib/types'

type CostMeterProps = Readonly<{
  cost: CostMessage
  variant: 'chip' | 'bar'
}>

const CAP_USD = 150
const WARN_USD = 90
const STOP_USD = 120
const TICKS: readonly number[] = [WARN_USD, STOP_USD]

function LockIcon(): React.JSX.Element {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 8 8"
      shapeRendering="crispEdges"
      fill={palette.moon}
      aria-hidden="true"
    >
      <rect x="2" y="0" width="4" height="1" />
      <rect x="2" y="1" width="1" height="2" />
      <rect x="5" y="1" width="1" height="2" />
      <rect x="1" y="3" width="6" height="5" />
    </svg>
  )
}

function Status({
  warn,
  stopped
}: Readonly<{ warn: boolean; stopped: boolean }>): React.JSX.Element | null {
  if (stopped) return <LockIcon />
  if (warn) {
    return (
      <span aria-hidden="true" className="text-gabi-ember">
        !
      </span>
    )
  }
  return null
}

function CostMeter({ cost, variant }: CostMeterProps): React.JSX.Element {
  const parsed = Number.parseFloat(cost.spent_usd)
  const spent = Number.isFinite(parsed) && parsed > 0 ? parsed : 0
  const fraction = Math.min(spent / CAP_USD, 1)
  const stopped = cost.stopped || spent >= STOP_USD
  const warn = cost.warn || spent >= WARN_USD
  const fill = stopped ? palette.sindak : warn ? palette.ember : palette.lantern
  const text = `$${spent.toFixed(2)} / $${CAP_USD}`
  const width = variant === 'bar' ? 480 : 160
  const height = variant === 'bar' ? 24 : 16
  const label = t('cost.label')

  const track = (
    <div
      className="relative border-2 border-gabi-ink bg-gabi-ink"
      style={{ width, height }}
      aria-hidden="true"
    >
      <div
        className="absolute left-0 top-0 h-full"
        style={{ width: `${fraction * 100}%`, background: fill }}
      />
      {TICKS.map((tick) => (
        <div
          key={tick}
          className="absolute top-0 h-full w-[2px] bg-gabi-moon"
          style={{ left: `${(tick / CAP_USD) * 100}%` }}
        />
      ))}
    </div>
  )

  const meterProps = {
    role: 'meter',
    'aria-label': pick(label),
    'aria-valuemin': 0,
    'aria-valuemax': CAP_USD,
    'aria-valuenow': Math.min(spent, CAP_USD),
    'aria-valuetext': text
  } as const

  if (variant === 'chip') {
    return (
      <div {...meterProps} className="panel flex items-center gap-3 px-4 py-2" title={pick(label)}>
        <Status warn={warn} stopped={stopped} />
        {track}
        <span>{text}</span>
      </div>
    )
  }

  return (
    <div {...meterProps} className="flex flex-col gap-1" style={{ width }}>
      <div className="flex items-center gap-3">
        <span>{pick(label)}</span>
        <Status warn={warn} stopped={stopped} />
        <span className="ml-auto">{text}</span>
      </div>
      {track}
      <div className="caption-en relative h-6" aria-hidden="true">
        {TICKS.map((tick) => (
          <span
            key={tick}
            className="absolute -translate-x-1/2"
            style={{ left: `${(tick / CAP_USD) * 100}%` }}
          >
            ${tick}
          </span>
        ))}
      </div>
    </div>
  )
}

export default CostMeter
