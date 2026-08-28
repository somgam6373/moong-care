import { useCallback, useRef, useState } from 'react'

export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const start = useCallback(async () => {
    setError(null)
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunksRef.current = []
      const recorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm;codecs=opus' })
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data)
      recorderRef.current = recorder
      setStream(mediaStream)
      recorder.start()
      setIsRecording(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setIsRecording(false)
    }
  }, [])

  const stop = useCallback((): Promise<Blob> => {
    return new Promise((resolve) => {
      const recorder = recorderRef.current
      if (!recorder) {
        resolve(new Blob([], { type: 'audio/webm' }))
        return
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream?.getTracks().forEach((track) => track.stop())
        setStream(null)
        setIsRecording(false)
        resolve(blob)
      }
      recorder.stop()
    })
  }, [stream])

  return { isRecording, error, stream, start, stop }
}
