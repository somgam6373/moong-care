import { describeBrightness } from '../constants/brightness'
import { getCareEmotionInfo } from '../constants/careEmotions'
import { useTranslation } from '../i18n/LanguageContext'

export function EmotionColorBar({ careEmotion, brightness }: { careEmotion: string; brightness: number }) {
  const { t, lang } = useTranslation()
  const info = getCareEmotionInfo(careEmotion)
  const label = lang === 'ko' ? info.labelKo : info.labelEn
  const colorName = lang === 'ko' ? info.colorNameKo : info.colorNameEn
  const careReason = lang === 'ko' ? info.careReasonKo : info.careReasonEn
  const brightnessText = describeBrightness(brightness, lang)

  return (
    <div style={{ display: 'flex', gap: 24, fontSize: 14, flexWrap: 'wrap', justifyContent: 'center' }}>
      <span>
        {t('yourEmotionLabel')} {label}
      </span>
      <span>
        {label}
        {t('colorSuffix')}: {colorName} ({brightnessText}) — {careReason}
      </span>
    </div>
  )
}
