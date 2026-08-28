import type { CSSProperties, ReactNode } from 'react'
import type { CareColor } from '../api/types'

// Pre-turn ambience, matches services/color_care_service.py REALTIME_COLORS['calm'].
const DEFAULT_COLOR: CareColor = { hex: '#A7CDBD', brightness: 0.42, transition_ms: 1600 }

function buildGradientStyle(color: CareColor | null): CSSProperties {
  const resolved = color ?? DEFAULT_COLOR
  return {
    background: `radial-gradient(circle at 50% 30%, ${resolved.hex}55 0%, ${resolved.hex}22 55%, transparent 100%)`,
    transition: `background ${resolved.transition_ms}ms ease`,
  }
}

export function EmotionAtmosphere({ color, children }: { color: CareColor | null; children: ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', width: '100%', ...buildGradientStyle(color) }}>
      {children}
    </div>
  )
}
