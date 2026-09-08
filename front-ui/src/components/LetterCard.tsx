import { useTranslation } from '../i18n/LanguageContext'
import { useTypewriter } from '../hooks/useTypewriter'

export function LetterCard({ dominantEmotionLabel, letterText }: { dominantEmotionLabel: string; letterText: string }) {
  const { t } = useTranslation()
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
      <div style={{ display: 'inline-block', padding: '8px 20px', borderRadius: 999, background: '#EADFC4', fontSize: 18, marginBottom: 28 }}>
        {t('todaysEmotionLabel')} {dominantEmotionLabel}
      </div>
      <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: 26 }}>{displayedText}</p>
    </div>
  )
}
