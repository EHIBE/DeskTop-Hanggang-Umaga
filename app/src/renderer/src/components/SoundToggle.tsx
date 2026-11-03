import { useSyncExternalStore } from 'react'
import { say } from '../lib/copy'
import { setSoundEnabled, soundEnabled, subscribeSound } from '../lib/sound'
import PixelIcon from './PixelIcon'

function SoundToggle(): React.JSX.Element {
  const on = useSyncExternalStore(subscribeSound, soundEnabled)
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      className="btn btn-quiet"
      onClick={() => setSoundEnabled(!on)}
    >
      <PixelIcon name={on ? 'check' : 'cross'} size={3} className={on ? 'text-gabi-dahon' : ''} />
      {say(on ? 'sfx.on' : 'sfx.off')}
    </button>
  )
}

export default SoundToggle
