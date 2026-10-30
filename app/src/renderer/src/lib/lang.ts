import { useSyncExternalStore } from 'react'

export type Lang = 'tl' | 'en'

const STORAGE_KEY = 'desktop.lang'

function readStored(): Lang | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    return value === 'tl' || value === 'en' ? value : null
  } catch {
    return null
  }
}

let chosen: Lang | null = readStored()
const listeners = new Set<() => void>()

export function currentLang(): Lang {
  return chosen ?? 'tl'
}

export function langChosen(): boolean {
  return chosen !== null
}

export function setLang(lang: Lang): void {
  chosen = lang
  try {
    window.localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    return
  } finally {
    listeners.forEach((listener) => listener())
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function snapshot(): Lang | null {
  return chosen
}

export function useLang(): Lang | null {
  return useSyncExternalStore(subscribe, snapshot)
}
