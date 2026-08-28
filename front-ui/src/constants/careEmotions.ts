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
export const CARE_EMOTIONS: Record<CareEmotionCode, CareEmotionInfo> = {
  calm: {
    labelKo: '평온', labelEn: 'Calm',
    colorNameKo: '부드러운 민트그린', colorNameEn: 'soft mint green',
    careReasonKo: '유지, 부드럽게 안정', careReasonEn: 'Stay calm and gently stable',
  },
  joy: {
    labelKo: '기쁨/만족', labelEn: 'Joy',
    colorNameKo: '따뜻한 골드', colorNameEn: 'warm gold',
    careReasonKo: '과각성 없이 따뜻하게 유지', careReasonEn: 'Keep the warmth without over-excitement',
  },
  excitement: {
    labelKo: '설렘/들뜸', labelEn: 'Excitement',
    colorNameKo: '맑은 하늘색', colorNameEn: 'clear sky blue',
    careReasonKo: '들뜸을 부드럽게 낮춤', careReasonEn: 'Gently ease the excitement',
  },
  relief: {
    labelKo: '안도', labelEn: 'Relief',
    colorNameKo: '산뜻한 연둣빛 그린', colorNameEn: 'fresh soft green',
    careReasonKo: '안정된 회복감 유지', careReasonEn: 'Maintain a settled sense of recovery',
  },
  sadness: {
    labelKo: '슬픔', labelEn: 'Sadness',
    colorNameKo: '따뜻한 살구빛', colorNameEn: 'warm apricot',
    careReasonKo: '따뜻하게 위로', careReasonEn: 'Offer warm comfort',
  },
  loneliness: {
    labelKo: '외로움', labelEn: 'Loneliness',
    colorNameKo: '포근한 라일락핑크', colorNameEn: 'soft lilac pink',
    careReasonKo: '포근함과 연결감 제공', careReasonEn: 'Provide warmth and a sense of connection',
  },
  anxiety: {
    labelKo: '불안', labelEn: 'Anxiety',
    colorNameKo: '차분한 블루', colorNameEn: 'calm blue',
    careReasonKo: '안정감과 호흡 유도', careReasonEn: 'Encourage calm, steady breathing',
  },
  tension: {
    labelKo: '긴장', labelEn: 'Tension',
    colorNameKo: '청량한 민트', colorNameEn: 'cool mint',
    careReasonKo: '차분하게 이완', careReasonEn: 'Help you relax calmly',
  },
  anger: {
    labelKo: '분노/짜증', labelEn: 'Anger',
    colorNameKo: '차분한 세이지그린', colorNameEn: 'calming sage green',
    careReasonKo: '진정, 탈각성', careReasonEn: 'Soothe and de-escalate',
  },
  stress: {
    labelKo: '스트레스/과부하', labelEn: 'Stress',
    colorNameKo: '고요한 세이지그린', colorNameEn: 'quiet sage green',
    careReasonKo: '과부하 완화', careReasonEn: 'Ease the overload',
  },
  fatigue: {
    labelKo: '피로', labelEn: 'Fatigue',
    colorNameKo: '따뜻한 앰버', colorNameEn: 'warm amber',
    careReasonKo: '회복감, 부담 완화', careReasonEn: 'Support recovery, lighten the load',
  },
  helplessness: {
    labelKo: '무기력', labelEn: 'Helplessness',
    colorNameKo: '포근한 베이지', colorNameEn: 'soft beige',
    careReasonKo: '낮은 자극으로 안정', careReasonEn: 'Settle with low stimulation',
  },
  confusion: {
    labelKo: '혼란/당황', labelEn: 'Confusion',
    colorNameKo: '은은한 라벤더', colorNameEn: 'gentle lavender',
    careReasonKo: '질서감과 안정', careReasonEn: 'Bring order and steadiness',
  },
  shame_guilt: {
    labelKo: '자책/민망함', labelEn: 'Shame/Guilt',
    colorNameKo: '부드러운 로즈베이지', colorNameEn: 'soft rose beige',
    careReasonKo: '부드러운 수용감 제공', careReasonEn: 'Offer gentle acceptance',
  },
}

export const FALLBACK_CARE_EMOTION: CareEmotionCode = 'calm'

export function getCareEmotionInfo(code: string): CareEmotionInfo {
  return CARE_EMOTIONS[code as CareEmotionCode] ?? CARE_EMOTIONS[FALLBACK_CARE_EMOTION]
}
