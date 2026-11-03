import { useEffect, useRef, useState } from 'react'
import LangToggle from '../components/LangToggle'
import NightScene from '../components/NightScene'
import PixelIcon from '../components/PixelIcon'
import SoundToggle from '../components/SoundToggle'
import TitleMark from '../components/TitleMark'
import { say, type CopyKey } from '../lib/copy'
import type { MessageHandler } from '../lib/socket'
import type { CampaignSummary, ClientMessage, Difficulty, StateMessage } from '../lib/types'

type StartProps = Readonly<{
  state: StateMessage
  send: (message: ClientMessage) => boolean
  subscribe: (handler: MessageHandler) => () => void
}>

const CONFIRM_MS = 4000

const DIFFICULTIES: readonly Difficulty[] = ['madali', 'normal', 'mahirap']

function difficultyKey(difficulty: Difficulty): CopyKey {
  return `diff.${difficulty}`
}

function Start({ state, send, subscribe }: StartProps): React.JSX.Element {
  const [campaigns, setCampaigns] = useState<readonly CampaignSummary[]>([])
  const [name, setName] = useState('')
  const [difficulty, setDifficulty] = useState<Difficulty>('normal')
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const confirmTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (confirmTimer.current !== null) clearTimeout(confirmTimer.current)
    }
  }, [])

  const armDelete = (id: string): void => {
    if (confirmTimer.current !== null) clearTimeout(confirmTimer.current)
    setConfirmId(id)
    confirmTimer.current = setTimeout(() => setConfirmId(null), CONFIRM_MS)
  }

  const deleteCampaign = (id: string): void => {
    if (confirmTimer.current !== null) clearTimeout(confirmTimer.current)
    setConfirmId(null)
    send({ type: 'campaign.delete', campaign_id: id })
  }

  useEffect(() => {
    const off = subscribe((message) => {
      if (message.type === 'campaigns') setCampaigns(message.campaigns)
    })
    send({ type: 'campaign.list' })
    return off
  }, [subscribe, send])

  const trimmed = name.trim()
  const valid = trimmed.length >= 1 && trimmed.length <= 40

  return (
    <main className="relative h-full w-full">
      <NightScene />
      <div className="absolute left-[160px] top-[112px] flex w-[720px] flex-col gap-16">
        <div className="rise-in">
          <TitleMark />
        </div>
        <form
          className="window rise-in flex flex-col gap-8 p-10"
          style={{ animationDelay: '120ms' }}
          onSubmit={(event) => {
            event.preventDefault()
            if (valid) send({ type: 'campaign.start', new: { name: trimmed, difficulty } })
          }}
        >
          <div className="flex flex-col gap-3">
            <label htmlFor="campaign-name" className="label">
              {say('start.name')}
            </label>
            <input
              id="campaign-name"
              type="text"
              maxLength={40}
              autoComplete="off"
              autoFocus
              placeholder={say('start.placeholder')}
              className="field w-full text-[24px]"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-3">
            <span id="difficulty-label" className="label">
              {say('start.difficulty')}
            </span>
            <div role="radiogroup" aria-labelledby="difficulty-label" className="segmented">
              {DIFFICULTIES.map((level) => (
                <button
                  key={level}
                  type="button"
                  role="radio"
                  aria-checked={level === difficulty}
                  onClick={() => setDifficulty(level)}
                >
                  {say(difficultyKey(level))}
                </button>
              ))}
            </div>
          </div>
          <button
            type="submit"
            className="btn btn-primary btn-big text-[32px] leading-[40px]"
            disabled={!valid}
          >
            <PixelIcon name="play" size={4} />
            {say('start.begin')}
          </button>
        </form>
      </div>

      {campaigns.length > 0 && (
        <section
          aria-labelledby="saves-title"
          className="window rise-in absolute left-[1040px] top-[320px] flex max-h-[440px] w-[640px] flex-col gap-4 p-8"
          style={{ animationDelay: '240ms' }}
        >
          <h2 id="saves-title" className="label">
            {say('start.saves')}
          </h2>
          <ul className="-mx-4 flex flex-col gap-1 overflow-y-auto px-4">
            {campaigns.map((campaign) => {
              const armed = confirmId === campaign.id
              return (
                <li key={campaign.id} className="flex items-stretch gap-2">
                  <button
                    type="button"
                    className="menu-row min-w-0 flex-1"
                    onClick={() => send({ type: 'campaign.start', campaign_id: campaign.id })}
                  >
                    <PixelIcon name="arrow" size={4} className="menu-cursor" />
                    <span className="flex min-w-0 flex-col gap-2">
                      <span className="truncate text-[24px] leading-[32px]">{campaign.name}</span>
                      <span className="flex items-center gap-3 text-gabi-mist">
                        {say(difficultyKey(campaign.difficulty))}
                        <PixelIcon name="moon" size={3} className="text-gabi-lantern" />
                        {campaign.nights_survived}
                      </span>
                    </span>
                  </button>
                  <button
                    type="button"
                    className={`btn btn-danger shrink-0 ${armed ? 'px-4' : 'w-[72px] px-0'}`}
                    data-armed={armed}
                    aria-label={`${say(armed ? 'delete.confirm' : 'start.delete')}: ${campaign.name}`}
                    title={say('start.delete')}
                    onClick={() => (armed ? deleteCampaign(campaign.id) : armDelete(campaign.id))}
                  >
                    {armed ? say('delete.confirm') : <PixelIcon name="trash" size={4} />}
                  </button>
                </li>
              )
            })}
          </ul>
        </section>
      )}

      <footer className="absolute bottom-[20px] left-[160px] right-[64px] flex items-center gap-8">
        <p className="flex items-center gap-3 text-gabi-mist">
          <PixelIcon name="arrow" size={3} className="text-gabi-lantern" />
          {say('start.tip')}
        </p>
        <div className="ml-auto flex items-center gap-4">
          <button
            type="button"
            role="switch"
            aria-checked={state.demo_safe}
            className="btn btn-quiet"
            title={say('start.demo_safe')}
            onClick={() => send({ type: 'demo_safe', on: !state.demo_safe })}
          >
            <PixelIcon
              name={state.demo_safe ? 'check' : 'wifi'}
              size={3}
              className={state.demo_safe ? 'text-gabi-dahon' : ''}
            />
            {say('start.demo_safe')}
          </button>
          {state.demo_safe && (
            <button
              type="button"
              role="switch"
              aria-checked={state.demo_safe_sam}
              className="btn btn-quiet"
              onClick={() => send({ type: 'demo_safe.sam', on: !state.demo_safe_sam })}
            >
              <PixelIcon
                name={state.demo_safe_sam ? 'check' : 'cross'}
                size={3}
                className={state.demo_safe_sam ? 'text-gabi-dahon' : ''}
              />
              {say('start.demo_safe_sam')}
            </button>
          )}
          <SoundToggle />
          <LangToggle />
        </div>
      </footer>
    </main>
  )
}

export default Start
