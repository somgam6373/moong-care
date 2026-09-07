import { useEffect, useRef, useState } from 'react'
import { analyzeVoice, synthesizeSpeech } from '../api/client'
import { EmotionAtmosphere } from '../components/EmotionAtmosphere'
import { EmotionColorBar } from '../components/EmotionColorBar'
import { MoongFace } from '../components/MoongFace'
import { PitchWaveform } from '../components/PitchWaveform'
import { SpeechBubble } from '../components/SpeechBubble'
import { useAudioRecorder } from '../hooks/useAudioRecorder'
import { useMicWaveform } from '../hooks/useMicWaveform'
import { useTranslation } from '../i18n/LanguageContext'
import { useConversation } from '../state/ConversationContext'

export function ConversationScreen() {
  const { t } = useTranslation()
  const { state, dispatch } = useConversation()
  const recorder = useAudioRecorder()
  const waveformSamples = useMicWaveform(recorder.stream)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [isSpeaking, setIsSpeaking] = useState(false)

  useEffect(() => {
    if (recorder.error) dispatch({ type: 'TURN_ERROR', message: recorder.error })
  }, [recorder.error, dispatch])

  async function handleMicClick() {
    if (!state.sessionId) return

    if (!recorder.isRecording) {
      dispatch({ type: 'RECORDING_STARTED' })
      await recorder.start()
      return
    }

    const audioBlob = await recorder.stop()
    dispatch({ type: 'RECORDING_STOPPED_ANALYZING' })

    try {
      const response = await analyzeVoice({ sessionId: state.sessionId, audioBlob })
      dispatch({
        type: 'TURN_SUCCESS',
        turn: {
          transcript: response.transcript,
          careEmotion: response.care_emotion,
          careColor: response.care_color,
          replyText: response.reply_text,
        },
      })

      try {
        const replyAudio = await synthesizeSpeech({ text: response.reply_text, sessionId: state.sessionId })
        const url = URL.createObjectURL(replyAudio)
        if (audioRef.current) {
          audioRef.current.src = url
          setIsSpeaking(true)
          await audioRef.current.play()
        }
      } catch (ttsError) {
        console.warn('TTS playback failed, continuing with text-only reply', ttsError)
      }
    } catch (err) {
      dispatch({ type: 'TURN_ERROR', message: err instanceof Error ? err.message : String(err) })
    }
  }

  const bubbleStatus = recorder.isRecording
    ? 'idle'
    : state.recordingStatus === 'analyzing'
      ? 'thinking'
      : state.currentTurn
        ? 'reply'
        : 'idle'

  return (
    <EmotionAtmosphere color={state.currentTurn?.careColor ?? null}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: 24, minHeight: '100vh' }}>
        <button
          onClick={() => dispatch({ type: 'END_REQUESTED' })}
          disabled={state.turnCount === 0}
          style={{ alignSelf: 'flex-end', marginTop: 48, padding: '8px 16px', borderRadius: 999, border: '1px solid #ccc', background: '#fff' }}
        >
          {t('endConversationButton')}
        </button>

        <SpeechBubble status={bubbleStatus} text={state.currentTurn?.replyText} />

        <MoongFace audioElement={audioRef.current} isSpeaking={isSpeaking} />
        <audio ref={audioRef} onEnded={() => setIsSpeaking(false)} style={{ display: 'none' }} />

        <PitchWaveform samples={waveformSamples} active={recorder.isRecording} />

        <button
          onClick={handleMicClick}
          disabled={state.recordingStatus === 'analyzing'}
          style={{
            padding: '12px 24px',
            borderRadius: 999,
            border: 'none',
            background: recorder.isRecording ? '#e07a5f' : '#85B8F2',
            color: '#fff',
          }}
        >
          {recorder.isRecording ? t('recordStop') : t('recordStart')}
        </button>

        {recorder.error && <p role="alert">{t('micPermissionDenied')}</p>}
        {state.turnErrorMessage && !recorder.error && <p role="alert">{t('networkErrorRetry')}</p>}

        {state.currentTurn && (
          <EmotionColorBar careEmotion={state.currentTurn.careEmotion} brightness={state.currentTurn.careColor.brightness} />
        )}
      </div>
    </EmotionAtmosphere>
  )
}
