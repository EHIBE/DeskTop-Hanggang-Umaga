import { useEffect, useRef, useState } from 'react'
import CostMeter from '../components/CostMeter'
import Bilingual from '../components/Bilingual'
import { t, type CopyKey } from '../lib/copy'
import type { MessageHandler } from '../lib/socket'
import type {
  CampaignSummary,
  ClientMessage,
  CostMessage,
  Difficulty,
  StateMessage
} from '../lib/types'

type StartProps = Readonly<{
  state: StateMessage
  send: (message: ClientMessage) => boolean
  subscribe: (handler: MessageHandler) => () => void
  cost: CostMessage | null
}>

const CONFIRM_MS = 4000

const DIFFICULTIES: readonly Difficulty[] = ['madali', 'normal', 'mahirap']

function difficultyKey(difficulty: Difficulty): CopyKey {
  return `diff.${difficulty}`
}

function Start({ state, send, subscribe, cost }: StartProps): React.JSX.Element {
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
    <main className="flex h-full w-full flex-col items-center gap-8 px-16 py-12">
      <Bilingual copyKey="start.ready" className="w-[1200px]" />
      <div className="flex w-[1600px] flex-1 gap-8 overflow-hidden">
        <form
          className="panel flex flex-1 flex-col gap-6 p-8"
          onSubmit={(event) => {
            event.preventDefault()
            if (valid) send({ type: 'campaign.start', new: { name: trimmed, difficulty } })
          }}
        >
          <h1 className="text-[24px] leading-[32px]">{t('start.new').tl}</h1>
          <label htmlFor="campaign-name">
            <Bilingual copyKey="start.name" />
          </label>
          <input
            id="campaign-name"
            type="text"
            maxLength={40}
            autoComplete="off"
            className="field w-full"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <div role="radiogroup" aria-label={t('start.difficulty').en} className="flex gap-4">
            {DIFFICULTIES.map((level) => {
              const active = level === difficulty
              return (
                <button
                  key={level}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  className="btn flex-1"
                  onClick={() => setDifficulty(level)}
                >
                  {active ? '> ' : ''}
                  {t(difficultyKey(level)).tl}
                </button>
              )
            })}
          </div>
          <button type="submit" className="btn btn-primary" disabled={!valid}>
            {t('start.begin').tl}
          </button>
        </form>
        <section className="panel flex flex-1 flex-col gap-6 overflow-y-auto p-8">
          <h2 className="text-[24px] leading-[32px]">{t('start.continue').tl}</h2>
          {campaigns.length === 0 ? (
            <Bilingual copyKey="start.empty" />
          ) : (
            <ul className="flex flex-col gap-4">
              {campaigns.map((campaign) => (
                <li key={campaign.id} className="flex items-stretch gap-8">
                  <button
                    type="button"
                    className="btn min-w-0 flex-1 text-left"
                    onClick={() => send({ type: 'campaign.start', campaign_id: campaign.id })}
                  >
                    <span className="block">{campaign.name}</span>
                    <span className="caption-en block">
                      {t(difficultyKey(campaign.difficulty)).tl}
                      {' - '}
                      {t('start.nights', { n: campaign.nights_survived }).tl}
                    </span>
                  </button>
                  <button
                    type="button"
                    className={`btn w-[200px] shrink-0 border-dashed border-gabi-sindak ${
                      confirmId === campaign.id ? 'bg-gabi-sindak' : ''
                    }`}
                    aria-label={`${t('start.delete').en}: ${campaign.name}`}
                    onClick={() =>
                      confirmId === campaign.id
                        ? deleteCampaign(campaign.id)
                        : armDelete(campaign.id)
                    }
                  >
                    {confirmId === campaign.id
                      ? `! ${t('delete.confirm').tl}`
                      : `X ${t('start.delete').tl}`}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      {cost !== null && <CostMeter cost={cost} variant="bar" />}
      <div className="flex items-center gap-4">
        <button
          type="button"
          role="switch"
          aria-checked={state.demo_safe}
          className="btn"
          onClick={() => send({ type: 'demo_safe', on: !state.demo_safe })}
        >
          {state.demo_safe ? '[x] ' : '[ ] '}
          {t('start.demo_safe').tl}
        </button>
        {state.demo_safe && (
          <button
            type="button"
            role="switch"
            aria-checked={state.demo_safe_sam}
            className="btn"
            onClick={() => send({ type: 'demo_safe.sam', on: !state.demo_safe_sam })}
          >
            {state.demo_safe_sam ? '[x] ' : '[ ] '}
            {t('start.demo_safe_sam').tl}
          </button>
        )}
      </div>
    </main>
  )
}

export default Start
