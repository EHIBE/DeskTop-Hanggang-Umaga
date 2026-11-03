import SpriteView from '../canvas/SpriteView'
import { say } from '../lib/copy'
import { playCue } from '../lib/sound'
import type { BadgeKind, ClientMessage, Progression, UnitSummary } from '../lib/types'
import PixelIcon from './PixelIcon'
import UnitMarks from './UnitMarks'

type BadgePanelProps = Readonly<{
  progression: Progression
  units: readonly UnitSummary[]
  send: (message: ClientMessage) => boolean
}>

function BadgePanel({ progression, units, send }: BadgePanelProps): React.JSX.Element | null {
  const rows = progression.badge_offers
    .map((offer) => ({ offer, unit: units.find((candidate) => candidate.id === offer.unit_id) }))
    .filter(
      (row): row is { offer: (typeof row)['offer']; unit: UnitSummary } => row.unit !== undefined
    )
  if (rows.length === 0) return null

  const pickBadge = (unitId: string, badge: BadgeKind): void => {
    if (send({ type: 'badge.pick', unit_id: unitId, badge })) playCue('badge')
  }

  return (
    <section
      aria-labelledby="badge-title"
      className="window flex max-h-[300px] w-[640px] flex-col gap-3 p-6"
    >
      <h2 id="badge-title" className="text-[24px] leading-[32px] text-gabi-lantern">
        {say('badge.title')}
      </h2>
      <ul className="-mx-2 flex min-h-0 flex-col gap-2 overflow-y-auto px-2">
        {rows.map(({ offer, unit }) => (
          <li
            key={unit.id}
            role="group"
            aria-label={say('badge.for', { unit: unit.name })}
            className="flex items-center gap-3"
          >
            <SpriteView
              unit={unit}
              scale={1}
              fallback={<span className="text-gabi-lantern">{unit.name.slice(0, 1)}</span>}
            />
            <span className="flex min-w-0 flex-1 items-center gap-2">
              <span className="min-w-0 truncate">{unit.name}</span>
              <UnitMarks badges={unit.badges} scars={unit.scars} />
            </span>
            {offer.choices.map((choice) => (
              <button
                key={choice}
                type="button"
                className="btn shrink-0 px-3"
                aria-label={`${say('badge.for', { unit: unit.name })}: ${say(
                  choice === 'hp' ? 'badge.hp' : 'badge.cooldown'
                )}`}
                onClick={() => pickBadge(unit.id, choice)}
              >
                <PixelIcon
                  name={choice === 'hp' ? 'heart' : 'bolt'}
                  size={3}
                  className={choice === 'hp' ? 'text-gabi-bukang' : 'text-gabi-lantern'}
                />
                {say(choice === 'hp' ? 'hud.hp' : 'hud.cd')}
              </button>
            ))}
          </li>
        ))}
      </ul>
    </section>
  )
}

export default BadgePanel
