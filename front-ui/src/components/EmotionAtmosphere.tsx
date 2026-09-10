import type { CSSProperties, ReactNode } from 'react'
import type { CareColor } from '../api/types'

// Pre-turn ambience, matches services/color_care_service.py REALTIME_COLORS['calm'].
const DEFAULT_COLOR: CareColor = { hex: '#88D1A6', brightness: 0.42, transition_ms: 1600 }

function buildGradientStyle(color: CareColor | null): CSSProperties {
  const resolved = color ?? DEFAULT_COLOR
  // A visible lamp-like glow: noticeably lighter at the top-center, ramping
  // up to the full, saturated palette color toward the edges. Still reads as
  // the correct palette hue throughout — never washed out to near-white.
  return {
    background: `radial-gradient(circle at 50% 20%, ${resolved.hex}99 0%, ${resolved.hex}dd 40%, ${resolved.hex} 85%)`,
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
