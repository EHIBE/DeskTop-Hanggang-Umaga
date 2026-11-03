import { useEffect, useRef, useState } from 'react'
import SpriteView from '../canvas/SpriteView'
import Bilingual from '../components/Bilingual'
import SpeakerChip from '../components/SpeakerChip'
import Captions from '../hud/Captions'
import { pick, say, t } from '../lib/copy'
import type { MessageHandler } from '../lib/socket'
import type { SpeakerSlot } from '../lib/speaker'
import type { ClientMessage, StateMessage } from '../lib/types'

type VoiceClaimProps = Readonly<{
  state: StateMessage
  send: (message: ClientMessage) => boolean
  subscribe: (handler: MessageHandler) => () => void
}>

const CLAIM_SECONDS = 60
const SLOTS = 4
const NAME_MAX = 24
const SLOT_KEYS = ['speaker.p1', 'speaker.p2', 'speaker.p3', 'speaker.p4'] as const
function slotOf(index: number): SpeakerSlot {
  return (index + 1) as SpeakerSlot
}

type Claims = Readonly<Record<string, number>>

function initialClaims(state: StateMessage): Claims {
  const players = state.night?.players ?? []
  const claims: Record<string, number> = {}
  state.night?.units.forEach((unit) => {
    const index = unit.owner === null ? -1 : players.indexOf(unit.owner)
    if (index >= 0 && index < SLOTS) claims[unit.id] = index
  })
  return claims
}

function initialNames(state: StateMessage): readonly string[] {
  const players = state.night?.players ?? []
  return Array.from({ length: SLOTS }, (_, index) => players[index] ?? '')
}

function VoiceClaim({ state, send, subscribe }: VoiceClaimProps): React.JSX.Element {
  const [names, setNames] = useState<readonly string[]>(() => initialNames(state))
  const [claims, setClaims] = useState<Claims>(() => initialClaims(state))
  const [selected, setSelected] = useState<string | null>(null)
  const [secondsLeft, setSecondsLeft] = useState(CLAIM_SECONDS)

  const serverKey = [
    (state.night?.players ?? []).join('|'),
    (state.night?.units ?? []).map((unit) => `${unit.id}=${unit.owner ?? ''}`).join('|')
  ].join('#')

  const latestRef = useRef(state)
  useEffect(() => {
    latestRef.current = state
  })

  useEffect(() => {
    const latest = latestRef.current
    const players = latest.night?.players ?? []
    setNames((current) =>
      current.map((name, index) => (players[index] !== undefined ? players[index] : name))
    )
    setClaims(initialClaims(latest))
  }, [serverKey])

  useEffect(() => {
    const timer = setInterval(() => setSecondsLeft((value) => Math.max(0, value - 1)), 1000)
    return () => clearInterval(timer)
  }, [])

  const trimmed = names.map((name) => name.trim())
  const duplicate = trimmed.map(
    (name, index) =>
      name !== '' &&
      trimmed.some(
        (other, otherIndex) => otherIndex !== index && other.toLowerCase() === name.toLowerCase()
      )
  )
  const anyDuplicate = duplicate.some(Boolean)
  const unitsOf = (index: number, map: Claims): string[] =>
    Object.keys(map).filter((id) => map[id] === index)
  const claimedCount = Object.keys(claims).length
  const ordered = [
    ...state.units.filter((unit) => unit.class === 'kubo'),
    ...state.units.filter((unit) => unit.class !== 'kubo')
  ]

  const sendClaim = (index: number, map: Claims): void => {
    send({ type: 'claim.tap', player_name: trimmed[index], unit_ids: unitsOf(index, map) })
  }

  const assign = (index: number): void => {
    if (selected === null || trimmed[index] === '' || duplicate[index]) return
    const previous = claims[selected]
    const next: Record<string, number> = { ...claims }
    if (previous === index) delete next[selected]
    else next[selected] = index
    setClaims(next)
    setSelected(null)
    sendClaim(index, next)
    if (previous !== undefined && previous !== index) sendClaim(previous, next)
  }

  const rename = (index: number, value: string): void => {
    setNames((current) => current.map((name, i) => (i === index ? value : name)))
  }

  const answer = (player: string, agree: boolean): void => {
    send({ type: 'consent', player_name: player, agree })
  }

  const done = (): void => {
    send({ type: 'claim.done' })
  }

  return (
    <main className="flex h-full w-full gap-8 p-8">
      <section className="panel flex min-w-0 flex-1 flex-col gap-6 p-6">
        <Bilingual copyKey="claim.prompt" />
        <Bilingual copyKey="claim.voice_hint" />
        <Captions
          subscribe={subscribe}
          players={state.night?.players ?? []}
          className="flex-none"
        />
        <p role="timer" className={secondsLeft <= 10 ? 'text-gabi-lantern' : 'caption-en'}>
          {secondsLeft <= 10 ? '! ' : ''}
          {say('claim.countdown', { seconds: secondsLeft })}
        </p>
        <h2 className="text-[24px] leading-[32px]">{say('summon.roster')}</h2>
        <ul className="flex flex-col gap-3 overflow-y-auto">
          {ordered.map((unit) => {
            const owner = claims[unit.id]
            return (
              <li key={unit.id}>
                <button
                  type="button"
                  className="btn flex w-full items-center gap-4 text-left"
                  aria-pressed={selected === unit.id}
                  onClick={() => setSelected(selected === unit.id ? null : unit.id)}
                >
                  <SpriteView
                    unit={unit}
                    scale={1}
                    fallback={<span className="text-gabi-lantern">{unit.name.slice(0, 1)}</span>}
                  />
                  <span className="min-w-0 flex-1 truncate">{unit.name}</span>
                  {owner === undefined ? (
                    <span className="shrink-0">{say('card.owner_none')}</span>
                  ) : (
                    <span className="flex min-w-0 shrink-0 items-center gap-2">
                      <SpeakerChip slot={slotOf(owner)} />
                      <span className="max-w-[160px] truncate">{trimmed[owner]}</span>
                    </span>
                  )}
                </button>
              </li>
            )
          })}
        </ul>
      </section>
      <aside className="panel flex w-[640px] shrink-0 flex-col gap-6 p-6">
        <h2 className="text-[24px] leading-[32px]">{say('claim.players')}</h2>
        {selected !== null ? (
          <Bilingual copyKey="claim.who" />
        ) : (
          <Bilingual copyKey="claim.tap_unit" />
        )}
        <div className="flex flex-col gap-4">
          {names.map((name, index) => {
            const label = t('claim.name_label', { n: index + 1 })
            const count = unitsOf(index, claims).length
            const ready = trimmed[index] !== '' && !duplicate[index]
            return (
              <div key={slotOf(index)} className="flex items-center gap-3">
                <SpeakerChip slot={slotOf(index)} />
                <input
                  className="field min-w-0 flex-1"
                  value={name}
                  maxLength={NAME_MAX}
                  aria-label={pick(label)}
                  placeholder={pick(label)}
                  aria-invalid={duplicate[index]}
                  disabled={count > 0}
                  onChange={(event) => rename(index, event.target.value)}
                />
                <button
                  type="button"
                  className="btn w-[160px] shrink-0 truncate"
                  disabled={!ready || selected === null}
                  aria-label={say(SLOT_KEYS[index])}
                  onClick={() => assign(index)}
                >
                  {ready ? trimmed[index] : `P${index + 1}`} {count > 0 ? count : ''}
                </button>
              </div>
            )
          })}
        </div>
        {anyDuplicate && (
          <p role="alert" className="caption-en">
            {say('claim.duplicate')}
          </p>
        )}
        {state.settings.replay_enabled && (
          <section aria-label={say('rec.consent')} className="flex flex-col gap-3">
            <Bilingual copyKey="rec.consent" />
            <Bilingual copyKey="rec.no_ok" />
            {(state.night?.players ?? []).map((player) => {
              const answered = Object.prototype.hasOwnProperty.call(state.consents, player)
              const agreed = answered && state.consents[player]
              const declined = answered && !state.consents[player]
              const label = t('rec.player', { name: player })
              return (
                <div
                  key={player}
                  role="group"
                  aria-label={pick(label)}
                  className="flex items-center gap-3"
                >
                  <span className="min-w-0 flex-1 truncate">
                    {agreed ? '✓ ' : declined ? '✗ ' : '? '}
                    {player}
                  </span>
                  <button
                    type="button"
                    className="btn w-[140px] shrink-0"
                    aria-pressed={agreed}
                    onClick={() => answer(player, true)}
                  >
                    {agreed ? '✓ ' : ''}
                    {say('rec.agree')}
                  </button>
                  <button
                    type="button"
                    className="btn w-[140px] shrink-0"
                    aria-pressed={declined}
                    onClick={() => answer(player, false)}
                  >
                    {declined ? '✗ ' : ''}
                    {say('rec.decline')}
                  </button>
                </div>
              )
            })}
            {Object.keys(state.consents).length === 0 && (
              <p className="caption-en">{say('rec.waiting')}</p>
            )}
          </section>
        )}
        <div className="mt-auto flex gap-4">
          <button type="button" className="btn flex-1" onClick={done}>
            {say('claim.skip')}
          </button>
          <button
            type="button"
            className="btn btn-primary flex-1"
            disabled={claimedCount === 0 || anyDuplicate}
            onClick={done}
          >
            {say('claim.done')}
          </button>
        </div>
      </aside>
    </main>
  )
}

export default VoiceClaim
