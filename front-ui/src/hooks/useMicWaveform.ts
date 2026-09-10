import { useEffect, useRef, useState } from 'react'

/** Live mic input samples (byte time-domain data) for a purely-visual "listening" waveform. */
export function useMicWaveform(stream: MediaStream | null): Uint8Array | null {
  const [samples, setSamples] = useState<Uint8Array | null>(null)
  const frameRef = useRef<number | null>(null)

  useEffect(() => {
    if (!stream) {
      setSamples(null)
      return
    }

    const audioContext = new AudioContext()
    const source = audioContext.createMediaStreamSource(stream)
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 2048
    source.connect(analyser)

    const buffer = new Uint8Array(analyser.frequencyBinCount)
    const tick = () => {
      analyser.getByteTimeDomainData(buffer)
      setSamples(new Uint8Array(buffer))
      frameRef.current = requestAnimationFrame(tick)
    }
    tick()

    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
      audioContext.close()
    }
  }, [stream])

  return samples
}
