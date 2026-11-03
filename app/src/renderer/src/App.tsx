import { useEffect, useState } from 'react'
import CostMeter from './components/CostMeter'
import Bilingual from './components/Bilingual'
import NightScene from './components/NightScene'
import Stage from './components/Stage'
import RecIndicator from './hud/RecIndicator'
import { isCopyKey, say, type CopyKey } from './lib/copy'
import { useLang } from './lib/lang'
import { armSoundUnlock } from './lib/sound'
import { useGameSocket } from './lib/socket'
import { useSoundCues } from './lib/useSoundCues'
import type {
  AppPhase,
  CopyParams,
  CostMessage,
  KeyStatus,
  NarrationMessage,
  StateMessage
} from './lib/types'
import Calibration from './screens/Calibration'
import KeySetup from './screens/KeySetup'
import LanguagePick from './screens/LanguagePick'
import Start from './screens/Start'
import Defeat from './screens/Defeat'
import Night from './screens/Night'
import Summon from './screens/Summon'
import Sunrise from './screens/Sunrise'
import VoiceClaim from './screens/VoiceClaim'

const NIGHT_PHASES: ReadonlySet<AppPhase> = new Set([
  'SPAWN_TELEGRAPH',
  'PLAYER_PHASE',
  'END_TURN_SNAPSHOT',
  'VALIDATE',
  'RESOLVE_PLAYER',
  'RESOLVE_ENEMY',
  'PHYSICAL_EFFECTS',
  'CHECK_END',
  'PAUSED'
])

const NARRATION_PHASES: ReadonlySet<AppPhase> = new Set([
  ...NIGHT_PHASES,
  'VOICE_CLAIM',
  'SUNRISE',
  'DEFEAT'
])

type ActiveNotice = Readonly<{ id: number; key: CopyKey; params: CopyParams }>

const NOTICE_MS = 6000

function Connecting(): React.JSX.Element {
  return (
    <main className="relative h-full w-full" role="status" aria-live="polite">
      <NightScene dim />
      <div className="absolute left-[160px] top-1/2 flex -translate-y-1/2 items-center gap-8">
        <div className="lantern" aria-hidden="true" />
        <Bilingual copyKey="restore" className="text-[24px] leading-[32px]" />
      </div>
    </main>
  )
}

function App(): React.JSX.Element {
  const { status, send, subscribe } = useGameSocket()
  const lang = useLang()
  const [state, setState] = useState<StateMessage | null>(null)
  const [keyStatus, setKeyStatus] = useState<KeyStatus | null>(null)
  const [offlineChosen, setOfflineChosen] = useState(false)
  const [cost, setCost] = useState<CostMessage | null>(null)
  const [notice, setNotice] = useState<ActiveNotice | null>(null)
  const [narration, setNarration] = useState<NarrationMessage | null>(null)

  useEffect(() => {
    return subscribe((message) => {
      if (message.type === 'state') {
        setState(message)
        if (!NARRATION_PHASES.has(message.phase)) setNarration(null)
      } else if (message.type === 'narration') {
        setNarration(message)
      } else if (message.type === 'cost') {
        setCost(message)
      } else if (
        message.type === 'notice' &&
        message.copy_key !== 'endturn.blocked' &&
        isCopyKey(message.copy_key)
      ) {
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

  useEffect(() => armSoundUnlock(), [])

  const ready = status === 'open' && state !== null && keyStatus !== null

  let screen: React.JSX.Element
  if (lang === null) {
    screen = <LanguagePick />
  } else if (!ready) {
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
    screen = <Start state={state} send={send} subscribe={subscribe} />
  } else if (state.phase === 'CALIBRATE') {
    screen = <Calibration state={state} send={send} subscribe={subscribe} />
  } else if (state.phase === 'VOICE_CLAIM') {
    screen = <VoiceClaim state={state} send={send} subscribe={subscribe} />
  } else if (NIGHT_PHASES.has(state.phase)) {
    screen = <Night state={state} send={send} subscribe={subscribe} narration={narration} />
  } else if (state.phase === 'SUNRISE') {
    screen = <Sunrise state={state} send={send} narration={narration} />
  } else if (state.phase === 'DEFEAT') {
    screen = <Defeat state={state} send={send} narration={narration} />
  } else {
    screen = <Summon state={state} send={send} subscribe={subscribe} />
  }
  const inNight = ready && NIGHT_PHASES.has(state.phase)
  useSoundCues(ready ? state : null, inNight)

  return (
    <Stage>
      {screen}
      {ready && lang !== null && (cost !== null || state.demo_safe) && (
        <div
          className={`absolute right-4 flex items-center gap-4 ${inNight ? 'bottom-[120px]' : 'top-4'}`}
        >
          {cost !== null && <CostMeter cost={cost} variant="chip" />}
          {state.demo_safe && !inNight && state.phase !== 'START' && (
            <div className="panel px-4 py-2">{say('start.demo_safe')}</div>
          )}
        </div>
      )}
      {ready && state.recording && (state.phase === 'SUNRISE' || state.phase === 'DEFEAT') && (
        <div className="panel absolute left-4 top-4 px-4 py-2">
          <RecIndicator />
        </div>
      )}
      {notice && (
        <div
          key={notice.id}
          role="status"
          aria-live="polite"
          className={`banner absolute left-1/2 w-[1200px] -translate-x-1/2 p-4 ${
            inNight ? 'top-[104px]' : 'top-4'
          }`}
        >
          <Bilingual copyKey={notice.key} params={notice.params} />
        </div>
      )}
    </Stage>
  )
}

export default App
