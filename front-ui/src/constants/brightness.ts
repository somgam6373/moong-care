export type Lang = 'ko' | 'en'

export function describeBrightness(brightness: number, lang: Lang): string {
  if (brightness >= 0.4) return lang === 'ko' ? '환하게' : 'brightly'
  if (brightness >= 0.3) return lang === 'ko' ? '포근하게' : 'warmly'
  return lang === 'ko' ? '은은하게' : 'softly'
}
