import { useTranslation } from '../i18n/LanguageContext'
import { useTypewriter } from '../hooks/useTypewriter'
import type { LetterLang } from '../state/ConversationContext'

export function LetterCard({
  dominantEmotionLabel,
  letterTextKo,
  letterTextEn,
  lang,
  onToggleLang,
}: {
  dominantEmotionLabel: string
  letterTextKo: string
  letterTextEn: string
  lang: LetterLang
  onToggleLang: () => void
}) {
  const { t } = useTranslation()
  const letterText = lang === 'ko' ? letterTextKo : letterTextEn
  const { displayedText } = useTypewriter(letterText, 30)

  return (
    <div
      style={{
        width: '100%',
        maxWidth: 880,
        margin: '0 auto',
        padding: '56px 64px',
        background: '#FBF3E3',
        border: '1px solid #E6D8B8',
        borderRadius: 20,
        boxShadow: '0 12px 44px rgba(0,0,0,0.16)',
        fontFamily: "'Gowun Dodum', sans-serif",
        boxSizing: 'border-box',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
        <div style={{ display: 'inline-block', padding: '8px 20px', borderRadius: 999, background: '#EADFC4', fontSize: 18 }}>
          {t('todaysEmotionLabel')} {dominantEmotionLabel}
        </div>
        <button
          onClick={onToggleLang}
          style={{ padding: '6px 16px', borderRadius: 999, border: '1px solid #E6D8B8', background: '#fff', fontSize: 14 }}
        >
          {lang === 'ko' ? 'EN' : '한글'}
        </button>
      </div>
      <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: 26 }}>{displayedText}</p>
    </div>
  )
}
