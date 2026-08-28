import { describe, expect, it } from 'vitest'
import { describeBrightness } from './brightness'

describe('describeBrightness', () => {
  it('describes high brightness (>= 0.4)', () => {
    expect(describeBrightness(0.5, 'ko')).toBe('환하게')
    expect(describeBrightness(0.4, 'en')).toBe('brightly')
  })

  it('describes mid brightness (0.3 - 0.4)', () => {
    expect(describeBrightness(0.35, 'ko')).toBe('포근하게')
    expect(describeBrightness(0.3, 'en')).toBe('warmly')
  })

  it('describes low brightness (< 0.3)', () => {
    expect(describeBrightness(0.12, 'ko')).toBe('은은하게')
    expect(describeBrightness(0.29, 'en')).toBe('softly')
  })
})
