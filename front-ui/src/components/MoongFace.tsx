import { useEffect, useRef, useState } from 'react'

// Placeholder circular face. Swap in the real illustration later — only these
// overlay coordinates need retuning, no logic changes.
const OVERLAY = {
  leftEye: { top: '38%', left: '30%', width: '12%', height: '12%' },
  rightEye: { top: '38%', left: '58%', width: '12%', height: '12%' },
  mouth: { top: '62%', left: '38%', width: '24%', height: '14%' },
}

function useBlinking(): boolean {
  const [eyesOpen, setEyesOpen] = useState(true)
  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout>
    const scheduleNext = () => {
      const delay = 2000 + Math.random() * 4000
      timeout = setTimeout(() => {
        setEyesOpen(false)
        timeout = setTimeout(() => {
          setEyesOpen(true)
          scheduleNext()
        }, 150)
      }, delay)
    }
    scheduleNext()
    return () => clearTimeout(timeout)
  }, [])
  return eyesOpen
}

function useMouthAmplitude(audioEl: HTMLAudioElement | null, isPlaying: boolean): number {
  const [amplitude, setAmplitude] = useState(0)
  const frameRef = useRef<number | null>(null)
  const contextRef = useRef<AudioContext | null>(null)
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null)

  useEffect(() => {
    if (!audioEl || !isPlaying) {
      setAmplitude(0)
      return
    }
    const audioContext = contextRef.current ?? new AudioContext()
    contextRef.current = audioContext
    // A given <audio> element can only ever be wrapped by one MediaElementSourceNode.
    const source = sourceRef.current ?? audioContext.createMediaElementSource(audioEl)
    sourceRef.current = source
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 1024
    source.connect(analyser)
    analyser.connect(audioContext.destination)

    const buffer = new Uint8Array(analyser.frequencyBinCount)
    const tick = () => {
      analyser.getByteFrequencyData(buffer)
      const average = buffer.reduce((sum, v) => sum + v, 0) / buffer.length
      setAmplitude(Math.min(1, average / 255))
      frameRef.current = requestAnimationFrame(tick)
    }
    tick()

    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
      analyser.disconnect()
    }
  }, [audioEl, isPlaying])

  return amplitude
}

export function MoongFace({ audioElement, isSpeaking }: { audioElement: HTMLAudioElement | null; isSpeaking: boolean }) {
  const eyesOpen = useBlinking()
  const mouthAmplitude = useMouthAmplitude(audioElement, isSpeaking)
  const eyeScaleY = eyesOpen ? 1 : 0.08
  const mouthScaleY = 0.35 + mouthAmplitude * 0.65

  return (
    <div
      style={{
        position: 'relative',
        width: 220,
        height: 220,
        borderRadius: '50%',
        background: '#FFF3D9',
        boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
      }}
      aria-label="뭉이"
    >
      <div
        style={{
          position: 'absolute', ...OVERLAY.leftEye,
          background: '#3a3a3a', borderRadius: '50%',
          transform: `scaleY(${eyeScaleY})`, transition: 'transform 80ms ease',
        }}
      />
      <div
        style={{
          position: 'absolute', ...OVERLAY.rightEye,
          background: '#3a3a3a', borderRadius: '50%',
          transform: `scaleY(${eyeScaleY})`, transition: 'transform 80ms ease',
        }}
      />
      <div
        style={{
          position: 'absolute', ...OVERLAY.mouth,
          background: '#B5544A', borderRadius: '0 0 40% 40% / 0 0 100% 100%',
          transform: `scaleY(${mouthScaleY})`, transformOrigin: 'top',
          transition: 'transform 60ms linear',
        }}
      />
    </div>
  )
}
