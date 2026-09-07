import { useEffect } from 'react'
import { endSession, generateDiary } from '../api/client'
import { EmotionAtmosphere } from '../components/EmotionAtmosphere'
import { LetterCard } from '../components/LetterCard'
import { getCareEmotionInfo } from '../constants/careEmotions'
import { useTranslation } from '../i18n/LanguageContext'
import { useConversation } from '../state/ConversationContext'

export function EndingScreen() {
  const { t, lang } = useTranslation()
  const { state, dispatch } = useConversation()
  const { sessionId, ending } = state

  useEffect(() => {
    if (!sessionId || ending.status !== 'loading' || ending.letterText) return
    let cancelled = false
    ;(async () => {
      try {
        const sessionResult = await endSession(sessionId)
        if (cancelled) return
        dispatch({ type: 'SESSION_ENDED', dominantEmotion: sessionResult.dominant_emotion, sleepColor: sessionResult.sleep_color })

        const diaryResult = await generateDiary(sessionId)
        if (cancelled) return
        dispatch({ type: 'DIARY_READY', letterText: diaryResult.letter_text })
      } catch (err) {
        if (!cancelled) dispatch({ type: 'ENDING_ERROR', message: err instanceof Error ? err.message : String(err) })
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, ending.status])

  const dominantInfo = ending.dominantEmotion ? getCareEmotionInfo(ending.dominantEmotion) : null
  const dominantLabel = dominantInfo ? (lang === 'ko' ? dominantInfo.labelKo : dominantInfo.labelEn) : ''

  return (
    <EmotionAtmosphere color={ending.sleepColor}>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 24, padding: 24 }}>
        {ending.status === 'error' && <p role="alert">{t('networkErrorRetry')}</p>}
        {(ending.status === 'loading' || (ending.status !== 'error' && !ending.letterText)) && <p>{t('loadingLetter')}</p>}
        {ending.letterText && dominantInfo && <LetterCard dominantEmotionLabel={dominantLabel} letterText={ending.letterText} />}
        <button
          onClick={() => dispatch({ type: 'RESET' })}
          style={{ padding: '10px 22px', borderRadius: 999, border: 'none', background: '#88D1A6' }}
        >
          {t('newConversationButton')}
        </button>
      </div>
    </EmotionAtmosphere>
  )
}
