import { describe, expect, it } from 'vitest'
import { getCareEmotionInfo } from './careEmotions'

describe('getCareEmotionInfo', () => {
  it('returns the known Korean/English labels for a valid code', () => {
    const info = getCareEmotionInfo('sadness')
    expect(info.labelKo).toBe('슬픔')
    expect(info.labelEn).toBe('Sadness')
    expect(info.colorNameKo).toBe('차분한 테라코타')
    expect(info.careReasonKo).toBe('따뜻하게 위로')
  })

  it('falls back to calm for an unknown code (matches backend FALLBACK_CARE_EMOTION)', () => {
    const info = getCareEmotionInfo('not_a_real_emotion')
    expect(info.labelKo).toBe('평온')
    expect(info.labelEn).toBe('Calm')
  })
})
