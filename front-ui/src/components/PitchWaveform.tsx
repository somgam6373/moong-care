function computeBarHeights(samples: Uint8Array | null, barCount: number): number[] {
  if (!samples || samples.length === 0) return new Array(barCount).fill(0)
  const bucketSize = Math.max(1, Math.floor(samples.length / barCount))
  const heights: number[] = []
  for (let i = 0; i < barCount; i++) {
    const start = i * bucketSize
    const end = Math.min(start + bucketSize, samples.length)
    let maxDeviation = 0
    for (let j = start; j < end; j++) maxDeviation = Math.max(maxDeviation, Math.abs(samples[j] - 128))
    heights.push(Math.min(1, maxDeviation / 128))
  }
  return heights
}

export function PitchWaveform({ samples, active, barCount = 24 }: { samples: Uint8Array | null; active: boolean; barCount?: number }) {
  const heights = active ? computeBarHeights(samples, barCount) : new Array(barCount).fill(0)
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 48 }}>
      {heights.map((h, i) => (
        <div
          key={i}
          style={{
            width: 4,
            height: `${Math.max(4, h * 100)}%`,
            background: '#8DB7D9',
            borderRadius: 2,
            transition: 'height 60ms linear',
          }}
        />
      ))}
    </div>
  )
}
