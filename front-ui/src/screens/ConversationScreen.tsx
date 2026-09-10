import { useEffect, useState } from 'react'
import { advanceMockTurn, USE_MOCK } from '../api/client'
import { EmotionAtmosphere } from '../components/EmotionAtmosphere'
import { EmotionBadges } from '../components/EmotionBadges'
import { MoongFace } from '../components/MoongFace'
import { SpeechBubble } from '../components/SpeechBubble'
import { useTranslation } from '../i18n/LanguageContext'
import { useConversation } from '../state/ConversationContext'

export function ConversationScreen() {
  const { t } = useTranslation()
  const { state, dispatch } = useConversation()
  const [isSpeaking, setIsSpeaking] = useState(false)

  // No real TTS audio to sync the mouth to in this poll-driven UI — estimate
  // a speaking duration from the reply length instead, so the mouth flaps
  // for roughly as long as 뭉이 would take to say it, then settles.
  useEffect(() => {
    const text = state.currentTurn?.replyText
    if (!text) return
    setIsSpeaking(true)
    const duration = Math.min(6000, Math.max(1200, text.length * 45))
    const timer = setTimeout(() => setIsSpeaking(false), duration)
    return () => clearTimeout(timer)
  }, [state.currentTurn?.replyText])

  const accentColor = state.currentTurn?.careColor.hex

  return (
    <EmotionAtmosphere color={state.currentTurn?.careColor ?? null}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 36,
          maxWidth: 640,
          margin: '0 auto',
          padding: '24px 24px 160px',
          minHeight: '100vh',
          boxSizing: 'border-box',
        }}
      >
        <SpeechBubble status={state.currentTurn ? 'reply' : 'idle'} text={state.currentTurn?.replyText} accentColor={accentColor} />

        <div
          onClick={USE_MOCK ? () => advanceMockTurn() : undefined}
          style={USE_MOCK ? { cursor: 'pointer' } : undefined}
        >
          <MoongFace size={300} isSpeaking={isSpeaking} />
        </div>

        {state.currentTurn && <EmotionBadges careEmotion={state.currentTurn.careEmotion} careColor={state.currentTurn.careColor} />}

        {USE_MOCK && <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.35)', margin: 0 }}>(mock) 클릭하면 다음 대화로 넘어가요</p>}

        {state.connectionIssue && <p role="alert">{t('networkErrorRetry')}</p>}
      </div>

      <button
        onClick={() => dispatch({ type: 'END_REQUESTED' })}
        disabled={!state.currentTurn}
        style={{
          position: 'fixed',
          bottom: 40,
          left: '50%',
          transform: 'translateX(-50%)',
          padding: '18px 56px',
          fontSize: 20,
          fontWeight: 700,
          letterSpacing: '0.01em',
          borderRadius: 999,
          border: 'none',
          background: state.currentTurn ? '#2a2a2e' : '#d9d9de',
          color: '#ffffff',
          boxShadow: state.currentTurn ? '0 12px 30px rgba(0,0,0,0.24)' : 'none',
          cursor: state.currentTurn ? 'pointer' : 'not-allowed',
          transition: 'background 200ms ease, box-shadow 200ms ease',
        }}
      >
        {t('endConversationButton')}
      </button>
    </EmotionAtmosphere>
  )
}
