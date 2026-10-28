import { resolve } from 'path'
import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const repoAssets = resolve(__dirname, '../assets')

export default defineConfig({
  main: {},
  preload: {},
  renderer: {
    resolve: {
      alias: {
        '@renderer': resolve('src/renderer/src'),
        '@assets': repoAssets
      }
    },
    server: {
      fs: {
        allow: [resolve(__dirname), repoAssets]
      }
    },
    plugins: [react(), tailwindcss()]
  }
})
