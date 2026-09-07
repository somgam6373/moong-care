export type CareEmotionCode =
  | 'calm'
  | 'joy'
  | 'excitement'
  | 'relief'
  | 'sadness'
  | 'loneliness'
  | 'anxiety'
  | 'tension'
  | 'anger'
  | 'stress'
  | 'fatigue'
  | 'helplessness'
  | 'confusion'
  | 'shame_guilt'

export interface CareEmotionInfo {
  labelKo: string
  labelEn: string
  colorNameKo: string
  colorNameEn: string
  careReasonKo: string
  careReasonEn: string
}

// Mirrors services/color_care_service.py CARE_EMOTION_LABELS + REALTIME_COLORS,
// and the "케어 방향" column in docs/prompts_Engineering/2026-08-13-emotion-care-mood-light-development-plan.md.
// Hex values themselves always come from the API response, never hardcoded here.
// colorName* reflects the 2026-08-29 color palette revision (higher saturation
// so colors stay distinguishable after the diffuser) — see color-palette-revision.md.
export const CARE_EMOTIONS: Record<CareEmotionCode, CareEmotionInfo> = {
  calm: {
    labelKo: '평온', labelEn: 'Calm',
    colorNameKo: '산뜻한 그린', colorNameEn: 'fresh green',
    careReasonKo: '유지, 부드럽게 안정', careReasonEn: 'Stay calm and gently stable',
  },
  joy: {
    labelKo: '기쁨/만족', labelEn: 'Joy',
    colorNameKo: '따뜻한 골드', colorNameEn: 'warm gold',
    careReasonKo: '과각성 없이 따뜻하게 유지', careReasonEn: 'Keep the warmth without over-excitement',
  },
  excitement: {
    labelKo: '설렘/들뜸', labelEn: 'Excitement',
    colorNameKo: '선명한 하늘색', colorNameEn: 'vivid sky blue',
    careReasonKo: '들뜸을 부드럽게 낮춤', careReasonEn: 'Gently ease the excitement',
  },
  relief: {
    labelKo: '안도', labelEn: 'Relief',
    colorNameKo: '생기있는 라임그린', colorNameEn: 'vivid lime green',
    careReasonKo: '안정된 회복감 유지', careReasonEn: 'Maintain a settled sense of recovery',
  },
  sadness: {
    labelKo: '슬픔', labelEn: 'Sadness',
    colorNameKo: '차분한 테라코타', colorNameEn: 'muted terracotta',
    careReasonKo: '따뜻하게 위로', careReasonEn: 'Offer warm comfort',
  },
  loneliness: {
    labelKo: '외로움', labelEn: 'Loneliness',
    colorNameKo: '차분한 오키드퍼플', colorNameEn: 'muted orchid purple',
    careReasonKo: '포근함과 연결감 제공', careReasonEn: 'Provide warmth and a sense of connection',
  },
  anxiety: {
    labelKo: '불안', labelEn: 'Anxiety',
    colorNameKo: '깊은 인디고블루', colorNameEn: 'deep indigo blue',
    careReasonKo: '안정감과 호흡 유도', careReasonEn: 'Encourage calm, steady breathing',
  },
  tension: {
    labelKo: '긴장', labelEn: 'Tension',
    colorNameKo: '청량한 민트', colorNameEn: 'cool mint',
    careReasonKo: '차분하게 이완', careReasonEn: 'Help you relax calmly',
  },
  anger: {
    labelKo: '분노/짜증', labelEn: 'Anger',
    colorNameKo: '차분한 틸블루', colorNameEn: 'calm teal-blue',
    careReasonKo: '진정, 탈각성', careReasonEn: 'Soothe and de-escalate',
  },
  stress: {
    labelKo: '스트레스/과부하', labelEn: 'Stress',
    colorNameKo: '차분한 블루그레이', colorNameEn: 'calm blue-gray',
    careReasonKo: '과부하 완화', careReasonEn: 'Ease the overload',
  },
  fatigue: {
    labelKo: '피로', labelEn: 'Fatigue',
    colorNameKo: '차분한 카키', colorNameEn: 'muted khaki',
    careReasonKo: '회복감, 부담 완화', careReasonEn: 'Support recovery, lighten the load',
  },
  helplessness: {
    labelKo: '무기력', labelEn: 'Helplessness',
    colorNameKo: '차분한 브라운베이지', colorNameEn: 'muted brown-beige',
    careReasonKo: '낮은 자극으로 안정', careReasonEn: 'Settle with low stimulation',
  },
  confusion: {
    labelKo: '혼란/당황', labelEn: 'Confusion',
    colorNameKo: '차분한 퍼플', colorNameEn: 'calm purple',
    careReasonKo: '질서감과 안정', careReasonEn: 'Bring order and steadiness',
  },
  shame_guilt: {
    labelKo: '자책/민망함', labelEn: 'Shame/Guilt',
    colorNameKo: '은은한 더스티로즈', colorNameEn: 'soft dusty rose',
    careReasonKo: '부드러운 수용감 제공', careReasonEn: 'Offer gentle acceptance',
  },
}

export const FALLBACK_CARE_EMOTION: CareEmotionCode = 'calm'

export function getCareEmotionInfo(code: string): CareEmotionInfo {
  return CARE_EMOTIONS[code as CareEmotionCode] ?? CARE_EMOTIONS[FALLBACK_CARE_EMOTION]
}
