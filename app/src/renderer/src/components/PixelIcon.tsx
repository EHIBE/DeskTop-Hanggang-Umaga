const GLYPHS = {
  arrow: ['#.....', '##....', '###...', '####..', '###...', '##....', '#.....'],
  check: ['......#', '.....##', '#...##.', '##.##..', '.###...', '..#....'],
  cross: ['#....#', '##..##', '.####.', '..##..', '.####.', '##..##', '#....#'],
  lock: ['..##..', '.#..#.', '.#..#.', '######', '##..##', '######', '######'],
  play: ['#....', '##...', '###..', '####.', '#####', '####.', '###..', '##...', '#....'],
  moon: ['..###.', '.##...', '##....', '##....', '##....', '.##...', '..###.'],
  sun: ['..#..', '#.#.#', '.###.', '#####', '.###.', '#.#.#', '..#..'],
  trash: ['.####.', '######', '.#..#.', '.#..#.', '.#..#.', '.####.'],
  camera: ['..##...', '#######', '##..###', '#.##.##', '##..###', '#######'],
  wifi: ['.####.', '#....#', '..##..', '.#..#.', '......', '..##..'],
  circle: ['.####.', '######', '######', '######', '######', '.####.'],
  square: ['######', '######', '######', '######', '######', '######'],
  triangle: ['..##..', '..##..', '.####.', '.####.', '######', '######'],
  diamond: ['..##..', '.####.', '######', '######', '.####.', '..##..']
} as const

export type IconName = keyof typeof GLYPHS

type PixelIconProps = Readonly<{
  name: IconName
  size?: number
  className?: string
}>

function PixelIcon({ name, size = 4, className = '' }: PixelIconProps): React.JSX.Element {
  const rows = GLYPHS[name]
  const width = Math.max(...rows.map((row) => row.length))
  const cells: React.JSX.Element[] = []
  rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x += 1) {
      if (row[x] === '#') cells.push(<rect key={`${x}:${y}`} x={x} y={y} width={1} height={1} />)
    }
  })
  return (
    <svg
      width={width * size}
      height={rows.length * size}
      viewBox={`0 0 ${width} ${rows.length}`}
      shapeRendering="crispEdges"
      fill="currentColor"
      aria-hidden="true"
      className={`shrink-0 ${className}`}
    >
      {cells}
    </svg>
  )
}

export default PixelIcon
