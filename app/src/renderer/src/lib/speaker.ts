export type SpeakerSlot = 1 | 2 | 3 | 4

const MAX_SLOTS = 4

export function speakerSlot(
  speaker: string | null | undefined,
  players: readonly string[]
): SpeakerSlot | null {
  if (!speaker) return null
  const wanted = speaker.trim().toLowerCase()
  const index = players.findIndex((player) => player.trim().toLowerCase() === wanted)
  if (index < 0 || index >= MAX_SLOTS) return null
  return (index + 1) as SpeakerSlot
}
