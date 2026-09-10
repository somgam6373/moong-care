import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'

export type Lang = 'ko' | 'en'

const DICT = {
  ko: {
    appTitle: '뭉이',
    introGreeting: '안녕, 나는 뭉이야. 오늘 하루 어땠는지 나한테 들려줄래?',
    startConversationButton: '대화 시작',
    recordStart: '눌러서 말하기',
    recordStop: '녹음 종료',
    thinking: '답변 고민 중',
    endConversationButton: '대화 종료',
    newConversationButton: '새 대화 시작',
    yourEmotionLabel: '사용자의 감정:',
    colorSuffix: '의 색상',
    currentEmotionLabel: '현재 사용자 감정:',
    healingColorLabel: '감정에 따른 치유 색상:',
    micPermissionDenied: '마이크 권한이 필요해요. 브라우저 설정에서 허용해줘.',
    networkErrorRetry: '연결에 문제가 생겼어. 다시 시도해줘.',
    loadingLetter: '뭉이가 편지를 쓰고 있어요...',
    todaysEmotionLabel: '오늘의 감정:',
    languageToggleLabel: 'EN',
    languageNote: '뭉이의 실제 대답은 항상 한국어로 나와요.',
  },
  en: {
    appTitle: 'Moong',
    introGreeting: "Hi, I'm Moong. Want to tell me about your day?",
    startConversationButton: 'Start talking',
    recordStart: 'Press to talk',
    recordStop: 'Stop recording',
    thinking: 'Thinking of a reply',
    endConversationButton: 'End conversation',
    newConversationButton: 'Start a new conversation',
    yourEmotionLabel: 'Your emotion:',
    colorSuffix: "'s color",
    currentEmotionLabel: 'Current user emotion:',
    healingColorLabel: 'Healing color for this emotion:',
    micPermissionDenied: 'Microphone access is needed. Please allow it in your browser settings.',
    networkErrorRetry: 'Something went wrong with the connection. Please try again.',
    loadingLetter: 'Moong is writing your letter...',
    todaysEmotionLabel: "Today's emotion:",
    languageToggleLabel: '한국어',
    languageNote: "Moong's actual replies are always in Korean.",
  },
} as const

export type DictKey = keyof (typeof DICT)['ko']

interface LanguageContextValue {
  lang: Lang
  setLang: (lang: Lang) => void
  t: (key: DictKey) => string
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>('ko')
  const value = useMemo<LanguageContextValue>(
    () => ({ lang, setLang, t: (key) => DICT[lang][key] }),
    [lang],
  )
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useTranslation(): LanguageContextValue {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useTranslation must be used within a LanguageProvider')
  return ctx
}
