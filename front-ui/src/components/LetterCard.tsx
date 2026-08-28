import { useTranslation } from '../i18n/LanguageContext'
import { useTypewriter } from '../hooks/useTypewriter'

export function LetterCard({ dominantEmotionLabel, letterText }: { dominantEmotionLabel: string; letterText: string }) {
  const { t } = useTranslation()
  const { displayedText } = useTypewriter(letterText, 30)

  return (
    <div
      style={{
        maxWidth: 480,
        margin: '0 auto',
        padding: '32px 28px',
        background: '#FBF3E3',
        border: '1px solid #E6D8B8',
        borderRadius: 12,
        boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
        fontFamily: 'Georgia, "Malgun Gothic", serif',
      }}
    >
      <div style={{ display: 'inline-block', padding: '4px 12px', borderRadius: 999, background: '#EADFC4', fontSize: 12, marginBottom: 16 }}>
        {t('todaysEmotionLabel')} {dominantEmotionLabel}
      </div>
      <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7, fontSize: 16 }}>{displayedText}</p>
    </div>
  )
}
