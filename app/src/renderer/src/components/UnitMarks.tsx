import { say } from '../lib/copy'
import type { BadgeKind } from '../lib/types'
import PixelIcon from './PixelIcon'

type UnitMarksProps = Readonly<{
  badges: readonly BadgeKind[]
  scars: number
  size?: number
  className?: string
}>

function UnitMarks({
  badges,
  scars,
  size = 2,
  className = ''
}: UnitMarksProps): React.JSX.Element | null {
  if (badges.length === 0 && scars <= 0) return null
  const label = [
    ...badges.map((badge) => say(badge === 'hp' ? 'badge.hp' : 'badge.cooldown')),
    ...(scars > 0 ? [`${say('scar.label')} ${scars}`] : [])
  ].join(', ')

  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className={`inline-flex shrink-0 items-center gap-1 ${className}`}
    >
      {badges.map((badge, index) => (
        <PixelIcon
          key={`${badge}:${index}`}
          name={badge === 'hp' ? 'heart' : 'bolt'}
          size={size}
          className={badge === 'hp' ? 'text-gabi-bukang' : 'text-gabi-lantern'}
        />
      ))}
      {scars > 0 && (
        <span className="inline-flex items-center gap-1 text-gabi-ember">
          <PixelIcon name="scar" size={size} />
          {scars > 1 && <span className="leading-[16px]">{scars}</span>}
        </span>
      )}
    </span>
  )
}

export default UnitMarks
