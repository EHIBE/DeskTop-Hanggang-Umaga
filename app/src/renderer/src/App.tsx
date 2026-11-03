import { useEffect, useMemo, useState } from 'react'
import CostMeter from './components/CostMeter'
import Bilingual from './components/Bilingual'
import NightScene from './components/NightScene'
import Stage from './components/Stage'
import RecIndicator from './hud/RecIndicator'
import { AssetsContext } from './lib/assets'
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
  MomentMessage,
  NarrationMessage,
  StateMessage
} from './lib/types'
import Calibration from './screens/Calibration'
import KeySetup from './screens/KeySetup'
import LanguagePick from './screens/LanguagePick'
import Start from './screens/Start'
import Defeat from './screens/Defeat'
import Night from './screens/Night'
import Recap from './screens/Recap'
import Settings from './screens/Settings'
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

const RECAP_PHASES: ReadonlySet<AppPhase> = new Set(['CALIBRATE', 'SUMMON', 'VOICE_CLAIM'])
const SETTINGS_PHASES: ReadonlySet<AppPhase> = new Set(['START', 'PAUSED'])

const NOTICE_MS = 6000
const MOMENT_MS = 8000
const CONNECT_STALL_MS = 45000

function Connecting(): React.JSX.Element {
  const [stalled, setStalled] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setStalled(true), CONNECT_STALL_MS)
    return () => clearTimeout(timer)
  }, [])

  return (
    <main className="relative h-full w-full" role="status" aria-live="polite">
      <NightScene dim />
      <div className="absolute left-[160px] top-1/2 flex -translate-y-1/2 items-center gap-8">
        <div className="lantern" aria-hidden="true" />
        <div className="flex flex-col gap-3">
          <Bilingual copyKey="restore" className="text-[24px] leading-[32px]" />
          {stalled && <Bilingual copyKey="conn.down" />}
        </div>
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
  const [moment, setMoment] = useState<MomentMessage | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [mapPng, setMapPng] = useState<string | null>(null)
  const [crops, setCrops] = useState<Readonly<Record<string, string>>>({})
  const [dismissedRecap, setDismissedRecap] = useState<string | null>(null)

  useEffect(() => {
    return subscribe((message) => {
      if (message.type === 'state') {
        setState(message)
        if (!NARRATION_PHASES.has(message.phase)) setNarration(null)
      } else if (message.type === 'narration') {
        setNarration(message)
      } else if (message.type === 'moment') {
        setMoment(message)
      } else if (message.type === 'map') {
        setMapPng(message.png)
      } else if (message.type === 'crops') {
        setCrops(message.crops)
      } else if (message.type === 'cost') {
        setCost(message)
      } else if (message.type === 'notice' && message.copy_key !== 'endturn.blocked') {
        const copyKey = message.copy_key
        if (isCopyKey(copyKey)) setNotice({ id: message.seq, key: copyKey, params: message.params })
        else setNotice({ id: message.seq, key: 'err.generic', params: {} })
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

  useEffect(() => {
    if (moment === null) return
    const timer = setTimeout(() => setMoment(null), MOMENT_MS)
    return () => clearTimeout(timer)
  }, [moment])

  useEffect(() => armSoundUnlock(), [])

  const ready = status === 'open' && state !== null && keyStatus !== null
  const campaignId = state?.campaign?.id ?? null
  const mapReady = ready && state.map.ready
  const wantCrops = ready && state.settings.show_real_objects
  const unitsKey = ready ? state.units.map((unit) => unit.unit_id).join(',') : ''
  const savedCaption = ready ? state.settings.caption_language : null

  useEffect(() => {
    if (mapReady) send({ type: 'map.get' })
  }, [mapReady, campaignId, send])

  useEffect(() => {
    if (wantCrops) send({ type: 'crops.get' })
  }, [wantCrops, unitsKey, send])

  useEffect(() => {
    if (lang !== null && savedCaption !== null && savedCaption !== lang) {
      send({ type: 'settings.set', key: 'caption_language', value: lang })
    }
  }, [lang, savedCaption, send])

  if (settingsOpen && ready && !SETTINGS_PHASES.has(state.phase)) setSettingsOpen(false)

  const assets = useMemo(
    () => ({ map: mapReady ? mapPng : null, crops: wantCrops ? crops : null }),
    [mapReady, mapPng, wantCrops, crops]
  )
  const recapKey = ready && state.recap !== null ? `${campaignId}:${state.recap.night}` : null
  const showRecap =
    ready &&
    state.recap !== null &&
    recapKey !== dismissedRecap &&
    RECAP_PHASES.has(state.phase) &&
    !settingsOpen

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
    screen = (
      <Start
        state={state}
        send={send}
        subscribe={subscribe}
        onOpenSettings={() => setSettingsOpen(true)}
      />
    )
  } else if (state.phase === 'CALIBRATE') {
    screen = <Calibration state={state} send={send} subscribe={subscribe} />
  } else if (state.phase === 'VOICE_CLAIM') {
    screen = <VoiceClaim state={state} send={send} subscribe={subscribe} />
  } else if (NIGHT_PHASES.has(state.phase)) {
    screen = (
      <Night
        state={state}
        send={send}
        subscribe={subscribe}
        narration={narration}
        moment={moment}
        onOpenSettings={() => setSettingsOpen(true)}
      />
    )
  } else if (state.phase === 'SUNRISE') {
    screen = <Sunrise state={state} send={send} narration={narration} moment={moment} />
  } else if (state.phase === 'DEFEAT') {
    screen = <Defeat state={state} send={send} narration={narration} moment={moment} />
  } else {
    screen = <Summon state={state} send={send} subscribe={subscribe} moment={moment} />
  }
  const inNight = ready && NIGHT_PHASES.has(state.phase)
  useSoundCues(ready ? state : null, inNight)

  return (
    <Stage>
      <AssetsContext.Provider value={assets}>{screen}</AssetsContext.Provider>
      {ready && settingsOpen && SETTINGS_PHASES.has(state.phase) && (
        <Settings
          state={state}
          send={send}
          subscribe={subscribe}
          onBack={() => setSettingsOpen(false)}
        />
      )}
      {showRecap && state.recap !== null && (
        <Recap recap={state.recap} onContinue={() => setDismissedRecap(recapKey)} />
      )}
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
