import { useTranslation } from '../i18n/LanguageContext'

export function SpeechBubble({ status, text }: { status: 'idle' | 'thinking' | 'reply'; text?: string }) {
  const { t } = useTranslation()
  if (status === 'idle') return null
  return (
    <div
      style={{
        background: '#ffffff',
        borderRadius: 16,
        padding: '10px 16px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.08)',
        maxWidth: 320,
        minHeight: 24,
      }}
    >
      <span aria-live="polite">{status === 'thinking' ? `${t('thinking')}...` : text}</span>
    </div>
  )
}
