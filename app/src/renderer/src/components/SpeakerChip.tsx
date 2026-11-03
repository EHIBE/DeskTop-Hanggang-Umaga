import type { CopyKey } from '../lib/copy'
import { say } from '../lib/copy'
import type { SpeakerSlot } from '../lib/speaker'
import PixelIcon from './PixelIcon'
import type { IconName } from './PixelIcon'

type SpeakerChipProps = Readonly<{
  slot: SpeakerSlot | null
  live?: boolean
  className?: string
}>

type Look = Readonly<{ icon: IconName; tone: string; label: CopyKey }>

const LOOKS: Readonly<Record<SpeakerSlot, Look>> = {
  1: { icon: 'circle', tone: 'border-gabi-lantern text-gabi-lantern', label: 'speaker.p1' },
  2: { icon: 'square', tone: 'border-gabi-dahon text-gabi-dahon', label: 'speaker.p2' },
  3: { icon: 'triangle', tone: 'border-gabi-bukang text-gabi-bukang', label: 'speaker.p3' },
  4: { icon: 'diamond', tone: 'border-gabi-mist text-gabi-mist', label: 'speaker.p4' }
}

const BASE = 'panel inline-flex h-[32px] shrink-0 items-center gap-2 px-2 leading-[16px]'

function SpeakerChip({ slot, live = false, className = '' }: SpeakerChipProps): React.JSX.Element {
  const pulse = live ? 'speaker-live' : ''
  if (slot === null) {
    return (
      <span
        role="img"
        aria-label={say('speaker.unknown')}
        className={`${BASE} border-gabi-dusk text-gabi-mist ${pulse} ${className}`}
      >
        <span aria-hidden="true">?</span>
      </span>
    )
  }
  const look = LOOKS[slot]
  return (
    <span
      role="img"
      aria-label={say(look.label)}
      className={`${BASE} ${look.tone} ${pulse} ${className}`}
    >
      <PixelIcon name={look.icon} size={2} />
      <span aria-hidden="true" className="text-gabi-moon">
        P{slot}
      </span>
    </span>
  )
}

export default SpeakerChip
