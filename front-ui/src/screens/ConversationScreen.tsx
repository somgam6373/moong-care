import { EmotionAtmosphere } from '../components/EmotionAtmosphere'
import { EmotionColorBar } from '../components/EmotionColorBar'
import { MoongFace } from '../components/MoongFace'
import { SpeechBubble } from '../components/SpeechBubble'
import { useTranslation } from '../i18n/LanguageContext'
import { useConversation } from '../state/ConversationContext'

export function ConversationScreen() {
  const { t } = useTranslation()
  const { state, dispatch } = useConversation()

  return (
    <EmotionAtmosphere color={state.currentTurn?.careColor ?? null}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: 24, minHeight: '100vh' }}>
        <button
          onClick={() => dispatch({ type: 'END_REQUESTED' })}
          disabled={!state.currentTurn}
          style={{ alignSelf: 'flex-end', marginTop: 48, padding: '8px 16px', borderRadius: 999, border: '1px solid #ccc', background: '#fff' }}
        >
          {t('endConversationButton')}
        </button>

        <SpeechBubble status={state.currentTurn ? 'reply' : 'idle'} text={state.currentTurn?.replyText} />

        <MoongFace />

        {state.connectionIssue && <p role="alert">{t('networkErrorRetry')}</p>}

        {state.currentTurn && (
          <EmotionColorBar careEmotion={state.currentTurn.careEmotion} brightness={state.currentTurn.careColor.brightness} />
        )}
      </div>
    </EmotionAtmosphere>
  )
}
