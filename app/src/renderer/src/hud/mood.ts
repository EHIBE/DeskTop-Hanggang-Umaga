import type { CopyKey } from '../lib/copy'
import type { NarrationMood } from '../lib/types'

export const MOOD_BORDER: Readonly<Record<NarrationMood, string>> = {
  kalmado: 'border-gabi-kawayan',
  kaba: 'border-gabi-ember',
  takot: 'border-gabi-sindak',
  tagumpay: 'border-gabi-lantern',
  umaga: 'border-gabi-liwayway'
}

export const MOOD_TEXT: Readonly<Record<NarrationMood, string>> = {
  kalmado: 'text-gabi-dahon',
  kaba: 'text-gabi-ember',
  takot: 'text-gabi-moon',
  tagumpay: 'text-gabi-lantern',
  umaga: 'text-gabi-liwayway'
}

export const MOOD_KEY: Readonly<Record<NarrationMood, CopyKey>> = {
  kalmado: 'narration.mood.kalmado',
  kaba: 'narration.mood.kaba',
  takot: 'narration.mood.takot',
  tagumpay: 'narration.mood.tagumpay',
  umaga: 'narration.mood.umaga'
}
