import { memo } from 'react'
import { palette } from '../lib/palette'

const STAGE_W = 1920
const PX = 8
const KUBO_PX = 12

function seeded(seed: number): () => number {
  let value = seed
  return () => {
    value = (value * 16807) % 2147483647
    return (value - 1) / 2147483646
  }
}

type Star = Readonly<{ x: number; y: number; big: boolean; delay: number; twinkle: boolean }>

const STARS: readonly Star[] = (() => {
  const rand = seeded(1121)
  return Array.from({ length: 70 }, () => ({
    x: Math.floor(rand() * (STAGE_W / 4)) * 4,
    y: Math.floor(rand() * 150) * 4,
    big: rand() > 0.86,
    delay: Math.round(rand() * 4000),
    twinkle: rand() > 0.55
  }))
})()

function canopy(seed: number, base: number, minR: number, maxR: number): string {
  const rand = seeded(seed)
  const rects: string[] = []
  let x = -32
  while (x < STAGE_W + 32) {
    const r = Math.round((minR + rand() * (maxR - minR)) / 8) * 8
    const lift = Math.round(rand() * 3) * 8
    for (let dx = -r; dx < r; dx += 8) {
      const h = Math.round(Math.sqrt(Math.max(0, r * r - (dx + 4) * (dx + 4))) / 8) * 8
      rects.push(`M${x + r + dx} ${base - lift - h}h8V320h-8z`)
    }
    x += Math.round(r * (1.1 + rand() * 0.6))
  }
  return rects.join('')
}

const FAR_CANOPY = canopy(77, 168, 48, 96)
const NEAR_CANOPY = canopy(311, 248, 40, 72)

const PALM = [
  '....##.##.....',
  '..##..#..##...',
  '.#...###...#..',
  '#...#.#.#...#.',
  '...#..#..#....',
  '......#.......',
  '.......#......',
  '.......#......',
  '.......#......',
  '......#.......',
  '......#.......',
  '......#.......',
  '.......#......',
  '.......#......',
  '.......#......',
  '.......#......'
]

const PALM_PATH = PALM.flatMap((row, y) =>
  [...row].map((cell, x) => (cell === '#' ? `M${x} ${y}h1v1h-1z` : ''))
).join('')

const PALMS = [
  { x: 72, scale: 16 },
  { x: 560, scale: 12 },
  { x: 1700, scale: 14 }
]

const MOON_R = 14
const MOON_CRATERS: ReadonlySet<string> = new Set([
  '-4,-5',
  '-3,-5',
  '-4,-4',
  '-3,-4',
  '5,2',
  '6,2',
  '5,3',
  '6,3',
  '7,3',
  '-6,5',
  '-5,5',
  '2,-8',
  '0,7',
  '1,7'
])

const MOON_CELLS: readonly Readonly<{ x: number; y: number; fill: string }>[] = (() => {
  const cells: { x: number; y: number; fill: string }[] = []
  for (let y = -MOON_R; y <= MOON_R; y += 1) {
    for (let x = -MOON_R; x <= MOON_R; x += 1) {
      const d = Math.sqrt(x * x + y * y)
      if (d > MOON_R) continue
      const shade = x + y > MOON_R * 0.9 || d > MOON_R - 1
      const fill = MOON_CRATERS.has(`${x},${y}`)
        ? palette.mist
        : shade
          ? palette.mist
          : palette.moon
      cells.push({ x: x + MOON_R, y: y + MOON_R, fill })
    }
  }
  return cells
})()

const KUBO = [
  '..........hh..........',
  '........hrrrrh........',
  '......hrrrrrrrrh......',
  '....hrrrrrrrrrrrrh....',
  '..hrrrrrrrrrrrrrrrrh..',
  'hrrrrrrrrrrrrrrrrrrrrh',
  '..wwwwwwwwwwwwwwwwww..',
  '..wwwLLLwwwwwwddwwww..',
  '..wwwLLLwwwwwwddwwww..',
  '..wwwwwwwwwwwwddwwww..',
  '..bbbbbbbbbbbbbbbbbb..',
  '...s....s....s....s...',
  '...s....s....s....s...',
  '...s....s....s....s...'
]

const KUBO_FILL: Readonly<Record<string, string>> = {
  h: palette.buhangin,
  r: palette.nipa,
  w: palette.dusk,
  b: palette.nipa,
  s: palette.night,
  d: palette.ink
}

const FIREFLIES = [
  { x: 1180, y: 840, delay: 0 },
  { x: 1320, y: 760, delay: 1400 },
  { x: 1560, y: 880, delay: 2600 },
  { x: 1720, y: 790, delay: 800 },
  { x: 980, y: 900, delay: 3300 },
  { x: 1460, y: 700, delay: 2000 }
]

type NightSceneProps = Readonly<{ dim?: boolean }>

function NightScene({ dim = false }: NightSceneProps): React.JSX.Element {
  const kuboW = KUBO[0].length * KUBO_PX
  const kuboH = KUBO.length * KUBO_PX
  return (
    <div className="scene" aria-hidden="true">
      <div className="scene-sky" />
      {STARS.map((star, index) => (
        <span
          key={index}
          className={`scene-star ${star.twinkle ? 'scene-twinkle' : ''}`}
          style={{
            left: star.x,
            top: star.y,
            width: star.big ? 8 : 4,
            height: star.big ? 8 : 4,
            animationDelay: `${star.delay}ms`
          }}
        />
      ))}
      <svg
        className="absolute"
        style={{ left: 1480, top: 96 }}
        width={(MOON_R * 2 + 1) * PX}
        height={(MOON_R * 2 + 1) * PX}
        viewBox={`0 0 ${MOON_R * 2 + 1} ${MOON_R * 2 + 1}`}
        shapeRendering="crispEdges"
      >
        {MOON_CELLS.map((cell) => (
          <rect
            key={`${cell.x}:${cell.y}`}
            x={cell.x}
            y={cell.y}
            width={1}
            height={1}
            fill={cell.fill}
          />
        ))}
      </svg>
      <svg
        className="absolute bottom-0 left-0"
        width={STAGE_W}
        height={320}
        viewBox={`0 0 ${STAGE_W} 320`}
        shapeRendering="crispEdges"
      >
        <path d={FAR_CANOPY} fill={palette.night} />
        <path d={NEAR_CANOPY} fill={palette.ink} />
      </svg>
      {PALMS.map((palm) => (
        <svg
          key={palm.x}
          className="absolute"
          style={{ left: palm.x, bottom: 40 }}
          width={PALM[0].length * palm.scale}
          height={PALM.length * palm.scale}
          viewBox={`0 0 ${PALM[0].length} ${PALM.length}`}
          shapeRendering="crispEdges"
        >
          <path d={PALM_PATH} fill={palette.ink} />
        </svg>
      ))}
      <svg
        className="absolute"
        style={{ left: 1240, bottom: 56 }}
        width={kuboW}
        height={kuboH}
        viewBox={`0 0 ${KUBO[0].length} ${KUBO.length}`}
        shapeRendering="crispEdges"
      >
        {KUBO.flatMap((row, y) =>
          [...row].map((cell, x) => {
            if (cell === '.') return null
            if (cell === 'L') {
              return (
                <rect key={`${x}:${y}`} className="scene-window" x={x} y={y} width={1} height={1} />
              )
            }
            return (
              <rect key={`${x}:${y}`} x={x} y={y} width={1} height={1} fill={KUBO_FILL[cell]} />
            )
          })
        )}
      </svg>
      {FIREFLIES.map((fly, index) => (
        <span
          key={index}
          className="scene-firefly"
          style={{ left: fly.x, top: fly.y, animationDelay: `${fly.delay}ms` }}
        />
      ))}
      <div className="absolute bottom-0 left-0 h-[64px] w-full bg-gabi-ink" />
      {dim && <div className="absolute inset-0 bg-gabi-ink/60" />}
    </div>
  )
}

export default memo(NightScene)
