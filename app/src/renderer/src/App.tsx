import { useEffect, useState } from 'react'
import CostMeter from './components/CostMeter'
import Bilingual from './components/Bilingual'
import Stage from './components/Stage'
import { isCopyKey, t, type CopyKey } from './lib/copy'
import { useGameSocket } from './lib/socket'
import type { CopyParams, CostMessage, KeyStatus, StateMessage } from './lib/types'
import Calibration from './screens/Calibration'
import KeySetup from './screens/KeySetup'
import Start from './screens/Start'
import Summon from './screens/Summon'

type ActiveNotice = Readonly<{ id: number; key: CopyKey; params: CopyParams }>

const NOTICE_MS = 6000

function Connecting(): React.JSX.Element {
  return (
    <main
      className="flex h-full w-full flex-col items-center justify-center gap-8"
      role="status"
      aria-live="polite"
    >
      <div className="lantern" aria-hidden="true" />
      <Bilingual copyKey="restore" className="text-center" />
    </main>
  )
}

function App(): React.JSX.Element {
  const { status, send, subscribe } = useGameSocket()
  const [state, setState] = useState<StateMessage | null>(null)
  const [keyStatus, setKeyStatus] = useState<KeyStatus | null>(null)
  const [offlineChosen, setOfflineChosen] = useState(false)
  const [cost, setCost] = useState<CostMessage | null>(null)
  const [notice, setNotice] = useState<ActiveNotice | null>(null)

  useEffect(() => {
    return subscribe((message) => {
      if (message.type === 'state') {
        setState(message)
      } else if (message.type === 'cost') {
        setCost(message)
      } else if (message.type === 'notice' && isCopyKey(message.copy_key)) {
        setNotice({ id: message.seq, key: message.copy_key, params: message.params })
      }
    })
  }, [subscribe])

  useEffect(() => {
    let active = true
    window.desktop
      .getKeyStatus()
      .then((result) => {
        if (active) setKeyStatus(result)
      })
      .catch(() => {
        if (active) setKeyStatus('missing')
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(null), NOTICE_MS)
    return () => clearTimeout(timer)
  }, [notice])

  const ready = status === 'open' && state !== null && keyStatus !== null

  let screen: React.JSX.Element
  if (!ready) {
    screen = <Connecting />
  } else if (keyStatus === 'missing' && !state.has_api_key && !state.demo_safe && !offlineChosen) {
    screen = (
      <KeySetup
        send={send}
        onKeyStatus={setKeyStatus}
        onContinueOffline={() => setOfflineChosen(true)}
      />
    )
  } else if (state.phase === 'START') {
    screen = <Start state={state} send={send} subscribe={subscribe} cost={cost} />
  } else if (state.phase === 'CALIBRATE') {
    screen = <Calibration state={state} send={send} subscribe={subscribe} />
  } else {
    screen = <Summon state={state} send={send} subscribe={subscribe} />
  }

  return (
    <Stage>
      {screen}
      {ready && (cost !== null || state.demo_safe) && (
        <div className="absolute right-4 top-4 flex items-center gap-4">
          {cost !== null && <CostMeter cost={cost} variant="chip" />}
          {state.demo_safe && <div className="panel px-4 py-2">{t('start.demo_safe').tl}</div>}
        </div>
      )}
      {notice && (
        <div
          key={notice.id}
          role="status"
          aria-live="polite"
          className="banner absolute left-1/2 top-4 w-[1200px] -translate-x-1/2 p-4"
        >
          <Bilingual copyKey={notice.key} params={notice.params} />
        </div>
      )}
    </Stage>
  )
}

export default App
