import SpriteView from '../canvas/SpriteView'
import UnitMarks from '../components/UnitMarks'
import { say } from '../lib/copy'
import StatusBadge from './StatusBadge'
import { nightUnitEntries, parseStatus } from './status'
import type { NightUnit, UnitSummary } from '../lib/types'

type UnitStripProps = Readonly<{
  units: readonly UnitSummary[]
  nightUnits: readonly NightUnit[]
  selectedId: string | null
  interactive: boolean
  onSelect: (id: string) => void
}>

function UnitStrip({
  units,
  nightUnits,
  selectedId,
  interactive,
  onSelect
}: UnitStripProps): React.JSX.Element {
  const rows = nightUnits
    .map((night) => ({ night, unit: units.find((candidate) => candidate.id === night.id) }))
    .filter((row): row is { night: NightUnit; unit: UnitSummary } => row.unit !== undefined)
    .sort((a, b) => Number(b.unit.class === 'kubo') - Number(a.unit.class === 'kubo'))

  return (
    <section
      aria-label={say('summon.roster')}
      className="panel flex w-[440px] shrink-0 flex-col gap-2 overflow-y-auto p-3"
    >
      {rows.map(({ night, unit }) => {
        const isKubo = unit.class === 'kubo'
        const status = parseStatus(night.status)
        const badges = nightUnitEntries(night)
        const selected = selectedId === unit.id
        const detail = [isKubo ? null : `${say('hud.cd')} ${night.cooldown}`, night.owner].filter(
          (part): part is string => part !== null && part !== ''
        )
        return (
          <button
            key={unit.id}
            type="button"
            className={`btn flex w-full items-center gap-3 px-3 py-1 text-left ${
              isKubo ? 'border-gabi-lantern' : ''
            } ${night.is_down || status.unavailable ? 'opacity-70' : ''}`}
            aria-pressed={selected}
            disabled={!interactive || night.is_down || isKubo || status.unavailable}
            onClick={() => onSelect(unit.id)}
          >
            <span className={night.is_down ? 'grayscale' : ''}>
              <SpriteView
                unit={unit}
                scale={1}
                fallback={<span className="text-gabi-lantern">{unit.name.slice(0, 1)}</span>}
              />
            </span>
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="flex justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="min-w-0 truncate">{unit.name}</span>
                  <UnitMarks badges={night.badges} scars={night.scars} />
                </span>
                <span className="shrink-0">
                  {say('hud.hp')} {night.hp}/{night.hp_max}
                </span>
              </span>
              <span className="caption-en flex flex-wrap gap-x-3 truncate">
                {badges.map((entry) => (
                  <StatusBadge key={entry.kind} entry={entry} />
                ))}
                <span className="truncate">
                  {night.is_down ? say('hud.down') : detail.join(' · ')}
                </span>
              </span>
            </span>
          </button>
        )
      })}
    </section>
  )
}

export default UnitStrip
