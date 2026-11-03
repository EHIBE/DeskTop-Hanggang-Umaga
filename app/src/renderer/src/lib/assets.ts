import { createContext, useContext } from 'react'

export type Assets = Readonly<{
  map: string | null
  crops: Readonly<Record<string, string>> | null
}>

export const AssetsContext = createContext<Assets>({ map: null, crops: null })

export function useAssets(): Assets {
  return useContext(AssetsContext)
}
