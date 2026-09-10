import { useState } from 'react'
import { startSession } from '../api/client'
import { MoongFace } from '../components/MoongFace'
import { useTranslation } from '../i18n/LanguageContext'
import { useConversation } from '../state/ConversationContext'

export function IntroScreen() {
  const { t } = useTranslation()
  const { dispatch } = useConversation()
  const [error, setError] = useState(false)

  async function handleStart() {
    setError(false)
    try {
      const { session_id } = await startSession()
      dispatch({ type: 'START_CONVERSATION', sessionId: session_id })
    } catch {
      setError(true)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 28 }}>
      <MoongFace size={280} />
      <h1 style={{ fontSize: 64, margin: 0 }}>{t('appTitle')}</h1>
      <p style={{ fontSize: 26, margin: 0, textAlign: 'center', maxWidth: 680 }}>{t('introGreeting')}</p>
      <button
        style={{ padding: '18px 44px', borderRadius: 999, border: 'none', background: '#A7CDBD', fontSize: 22, fontWeight: 600 }}
        onClick={handleStart}
      >
        {t('startConversationButton')}
      </button>
      {error && <p role="alert">{t('networkErrorRetry')}</p>}
    </div>
  )
}
