import { useEffect, useRef, useState } from 'react'

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
  const mouthScaleY = 0.6 + mouthAmplitude * 0.9

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width={220}
      height={220}
      aria-label="뭉이"
      style={{ filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.12))' }}
    >
      <circle cx="32" cy="32" r="32" fill="#f3cdb9" />
      <path
        d="M30,8 C42,8 52,16 54,28 C62,30 62,42 54,46 C54,56 44,60 34,58 C26,62 14,58 12,50 C4,48 4,36 12,32 C12,20 20,8 30,8 Z"
        fill="#fffdf8"
        stroke="#221f1c"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <circle cx="20" cy="36" r="1.8" fill="#f3cdb9" />
      <circle cx="44" cy="36" r="1.8" fill="#f3cdb9" />
      <circle
        cx="25" cy="30" r="2" fill="#221f1c"
        style={{ transform: `scaleY(${eyeScaleY})`, transformOrigin: '25px 30px', transition: 'transform 80ms ease' }}
      />
      <circle
        cx="39" cy="30" r="2" fill="#221f1c"
        style={{ transform: `scaleY(${eyeScaleY})`, transformOrigin: '39px 30px', transition: 'transform 80ms ease' }}
      />
      <path
        d="M28 38 q4 4 8 0"
        fill="none"
        stroke="#221f1c"
        strokeWidth="1.8"
        strokeLinecap="round"
        style={{ transform: `scaleY(${mouthScaleY})`, transformOrigin: '32px 38px', transition: 'transform 60ms linear' }}
      />
    </svg>
  )
}
