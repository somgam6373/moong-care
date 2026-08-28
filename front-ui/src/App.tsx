import { LanguageProvider, useTranslation } from './i18n/LanguageContext'
import { ConversationProvider, useConversation } from './state/ConversationContext'
import { IntroScreen } from './screens/IntroScreen'
import { ConversationScreen } from './screens/ConversationScreen'
import { EndingScreen } from './screens/EndingScreen'

function LanguageToggle() {
  const { lang, setLang, t } = useTranslation()
  return (
    <div style={{ position: 'fixed', top: 12, right: 12, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, zIndex: 10 }}>
      <button
        onClick={() => setLang(lang === 'ko' ? 'en' : 'ko')}
        style={{ padding: '4px 12px', borderRadius: 999, border: '1px solid #ccc', background: '#fff', fontSize: 12 }}
      >
        {t('languageToggleLabel')}
      </button>
      <span style={{ fontSize: 11, color: '#777', maxWidth: 180, textAlign: 'right' }}>{t('languageNote')}</span>
    </div>
  )
}

function Screens() {
  const { state } = useConversation()
  if (state.screen === 'intro') return <IntroScreen />
  if (state.screen === 'conversation') return <ConversationScreen />
  return <EndingScreen />
}

export default function App() {
  return (
    <LanguageProvider>
      <ConversationProvider>
        <LanguageToggle />
        <Screens />
      </ConversationProvider>
    </LanguageProvider>
  )
}
