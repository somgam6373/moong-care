import { useTranslation } from '../i18n/LanguageContext'

export function SpeechBubble({
  status,
  text,
  accentColor,
}: {
  status: 'idle' | 'thinking' | 'reply'
  text?: string
  accentColor?: string
}) {
  const { t } = useTranslation()
  if (status === 'idle') return null
  return (
    <div style={{ position: 'relative', maxWidth: 640, width: '100%' }}>
      <div
        style={{
          background: '#ffffff',
          borderRadius: 28,
          padding: '22px 32px',
          boxShadow: '0 10px 32px rgba(0,0,0,0.10)',
          borderTop: `4px solid ${accentColor ?? '#e5e5ea'}`,
          minHeight: 32,
          transition: 'border-color 400ms ease',
        }}
      >
        <span aria-live="polite" style={{ fontSize: 28, fontWeight: 600, lineHeight: 1.45, color: '#222' }}>
          {status === 'thinking' ? `${t('thinking')}...` : text}
        </span>
      </div>
      {/* Tail pointing down toward 뭉이 */}
      <div
        style={{
          position: 'absolute',
          bottom: -8,
          left: '50%',
          width: 18,
          height: 18,
          background: '#ffffff',
          transform: 'translateX(-50%) rotate(45deg)',
          borderRadius: '0 0 4px 0',
          boxShadow: '4px 4px 10px rgba(0,0,0,0.04)',
        }}
      />
    </div>
  )
}
