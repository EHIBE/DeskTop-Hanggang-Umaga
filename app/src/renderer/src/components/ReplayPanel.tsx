import { useState } from 'react'
import { say } from '../lib/copy'
import type { ClientMessage, ReplayState } from '../lib/types'
import Bilingual from './Bilingual'

type ReplayPanelProps = Readonly<{
  replay: ReplayState
  hadPlayers: boolean
  send: (message: ClientMessage) => boolean
}>

function ReplayPanel({ replay, hadPlayers, send }: ReplayPanelProps): React.JSX.Element | null {
  const [missing, setMissing] = useState(false)

  const request = (): void => {
    setMissing(false)
    send({ type: 'replay.request' })
  }

  const show = (): void => {
    if (replay.file === null) {
      setMissing(true)
      return
    }
    window.desktop
      .showReel(replay.file)
      .then((opened) => setMissing(!opened))
      .catch(() => setMissing(true))
  }

  if (!replay.available) {
    if (!hadPlayers) return null
    return <p className="caption-en">{say('replay.none')}</p>
  }

  const working = replay.status === 'working'

  return (
    <div className="flex flex-col items-start gap-3" role="status" aria-live="polite">
      {working && <Bilingual copyKey="replay.making" />}
      {replay.status === 'done' && <Bilingual copyKey="replay.done" />}
      {replay.status === 'failed' && <Bilingual copyKey="replay.failed" />}
      {missing && <Bilingual copyKey="replay.missing" />}
      <div className="flex gap-6">
        {(replay.status === 'idle' || replay.status === 'working') && (
          <button type="button" className="btn" disabled={working} onClick={request}>
            {say('replay.make')}
          </button>
        )}
        {replay.status === 'failed' && (
          <button type="button" className="btn" onClick={request}>
            {say('replay.make')}
          </button>
        )}
        {replay.status === 'done' && (
          <button type="button" className="btn" onClick={show}>
            {say('replay.show')}
          </button>
        )}
      </div>
    </div>
  )
}

export default ReplayPanel
