import { useEffect, useRef, useState } from 'react'
import PixelIcon from '../components/PixelIcon'
import { say } from '../lib/copy'
import {
  HINT_KEYS,
  nextHint,
  readSeen,
  reservesHintSlot,
  writeSeen,
  type HintKey
} from '../lib/tutorial'
import type { AppPhase, NightSummary } from '../lib/types'

type HintStripProps = Readonly<{
  campaignId: string | null
  phase: AppPhase
  night: NightSummary
  voiceOff: boolean
}>

const AUTO_ADVANCE_MS = 8000

function HintStrip({
  campaignId,
  phase,
  night,
  voiceOff
}: HintStripProps): React.JSX.Element | null {
  const [seen, setSeen] = useState<ReadonlySet<HintKey>>(() =>
    campaignId === null ? new Set() : readSeen(campaignId)
  )
  const [seenAtMount] = useState<ReadonlySet<HintKey>>(seen)
  const hint = campaignId === null ? null : nextHint({ phase, night, seen })

  const markRef = useRef<(keys: readonly HintKey[]) => void>(() => undefined)
  useEffect(() => {
    markRef.current = (keys) => {
      if (campaignId === null) return
      const next = new Set([...seen, ...keys])
      writeSeen(campaignId, next)
      setSeen(next)
    }
  })

  useEffect(() => {
    if (hint === null) return
    const timer = setTimeout(() => markRef.current([hint]), AUTO_ADVANCE_MS)
    return () => clearTimeout(timer)
  }, [hint])

  if (hint === null) {
    if (campaignId === null || !reservesHintSlot(night, seenAtMount)) return null
    return <div aria-hidden="true" className="mx-4 mb-2 h-14 shrink-0" />
  }

  const textKey = hint === 'tut.order' && voiceOff ? 'tut.order_tap' : hint

  return (
    <div
      key={hint}
      role="status"
      aria-live="polite"
      className="banner hint-strip mx-4 mb-2 flex h-14 shrink-0 items-center gap-4 px-4"
    >
      <PixelIcon name="arrow" size={3} className="text-gabi-lantern" />
      <p className="min-w-0 flex-1 whitespace-nowrap text-[24px] leading-[32px] text-gabi-moon">
        {say(textKey)}
      </p>
      <button
        type="button"
        className="btn btn-quiet px-4"
        aria-label={say('tut.dismiss')}
        onClick={() => markRef.current([hint])}
      >
        <PixelIcon name="cross" size={3} />
        {say('tut.dismiss')}
      </button>
      <button
        type="button"
        className="btn btn-quiet px-4"
        onClick={() => markRef.current(HINT_KEYS)}
      >
        {say('tut.skip_all')}
      </button>
    </div>
  )
}

export default HintStrip
