import { useEffect, useRef, useState } from 'react'
import { t } from '../lib/copy'
import type { MessageHandler } from '../lib/socket'

type CaptionsProps = Readonly<{
  subscribe: (handler: MessageHandler) => () => void
  className?: string
}>

type Line = Readonly<{ turnId: string; text: string; speaker: string | null }>

const FINAL_MS = 4000

function Captions({ subscribe, className = '' }: CaptionsProps): React.JSX.Element {
  const [partial, setPartial] = useState<Line | null>(null)
  const [final, setFinal] = useState<Line | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const clearTimer = (): void => {
      if (timerRef.current !== null) clearTimeout(timerRef.current)
      timerRef.current = null
    }
    const off = subscribe((message) => {
      if (message.type !== 'caption') return
      const line: Line = {
        turnId: message.turn_id,
        text: message.text,
        speaker: message.speaker
      }
      if (message.is_final) {
        setPartial((current) =>
          current !== null && current.turnId === line.turnId ? null : current
        )
        if (line.text.trim() === '') return
        setFinal(line)
        clearTimer()
        timerRef.current = setTimeout(() => {
          timerRef.current = null
          setFinal(null)
        }, FINAL_MS)
      } else {
        setPartial(line)
      }
    })
    return () => {
      off()
      clearTimer()
    }
  }, [subscribe])

  const showPartial = partial !== null && partial.text.trim() !== ''

  return (
    <section
      aria-label={t('voice.caption_label').en}
      aria-live="polite"
      className={`flex min-h-[48px] min-w-0 flex-1 flex-col justify-center border-2 border-gabi-dusk bg-gabi-night px-4 py-1 ${className}`}
    >
      {showPartial && (
        <p className="truncate leading-[24px] text-gabi-mist">
          {partial.speaker !== null && (
            <span className="mr-2 text-gabi-lantern">{partial.speaker}:</span>
          )}
          <span>{partial.text}</span>
        </p>
      )}
      {final !== null && !showPartial && (
        <p className="truncate leading-[24px] text-gabi-moon">
          {final.speaker !== null && (
            <span className="mr-2 text-gabi-lantern">{final.speaker}:</span>
          )}
          <span>{final.text}</span>
        </p>
      )}
    </section>
  )
}

export default Captions
