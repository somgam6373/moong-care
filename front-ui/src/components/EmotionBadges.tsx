import type { CSSProperties } from 'react'
import type { CareColor } from '../api/types'
import { getCareEmotionInfo } from '../constants/careEmotions'
import { useTranslation } from '../i18n/LanguageContext'

const chipStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  padding: '14px 24px',
  borderRadius: 999,
  background: 'rgba(255,255,255,0.78)',
  boxShadow: '0 3px 14px rgba(0,0,0,0.07)',
  backdropFilter: 'blur(8px)',
  WebkitBackdropFilter: 'blur(8px)',
}

const labelStyle: CSSProperties = {
  fontSize: 15,
  fontWeight: 700,
  letterSpacing: '0.03em',
  color: '#75757e',
  whiteSpace: 'nowrap',
}

const valueStyle: CSSProperties = {
  fontSize: 20,
  fontWeight: 700,
  color: '#2a2a2e',
  whiteSpace: 'nowrap',
}

export function EmotionBadges({ careEmotion, careColor }: { careEmotion: string; careColor: CareColor }) {
  const { t, lang } = useTranslation()
  const info = getCareEmotionInfo(careEmotion)
  const emotionLabel = lang === 'ko' ? info.labelKo : info.labelEn
  const colorName = lang === 'ko' ? info.colorSimpleKo : info.colorSimpleEn

  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
      <div style={chipStyle}>
        <span style={labelStyle}>{t('currentEmotionLabel')}</span>
        <span style={valueStyle}>{emotionLabel}</span>
      </div>
      <div style={chipStyle}>
        <span
          aria-hidden
          style={{
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: careColor.hex,
            boxShadow: `0 0 0 4px ${careColor.hex}2E`,
            flexShrink: 0,
          }}
        />
        <span style={labelStyle}>{t('healingColorLabel')}</span>
        <span style={valueStyle}>{colorName}</span>
      </div>
    </div>
  )
}
