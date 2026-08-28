# MoongCare front-ui Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the React+TypeScript+Vite web frontend at `moong-care/front-ui/` for the MoongCare voice-conversation mood-light service, wired to the existing FastAPI backend with zero backend changes.

**Architecture:** Three-screen state machine (Intro → Conversation → Ending) driven by a single `useReducer` in `ConversationContext`. The Conversation screen is the core loop: record → `POST /api/v1/voice/analyze` → show reply + emotion color → `POST /api/v1/tts` → play audio while animating the mascot's mouth. Ending screen calls `POST /api/v1/session/end` then `POST /api/v1/diary/generate` (in that order, because the server caches `sleep_color` from the first call and reuses it in the second) and reveals `letter_text` in a letter-styled card.

**Tech Stack:** React 18, TypeScript 5, Vite 5, Vitest 2 + @testing-library/react for tests. No external state-management or CSS framework libraries (plain CSS, React Context).

## Global Constraints

- Do not modify anything outside `moong-care/front-ui/` and `moong-care/.claude/launch.json` — the FastAPI backend (`routers/`, `services/`, `models/`, `database/`) is off-limits.
- `front-ui/` lives inside the `moong-care` git repo (`moong-care/front-ui/`), not the sibling location.
- API base URL comes from `VITE_API_BASE_URL` (Vite env var), default `http://localhost:8000`.
- Only UI chrome (buttons/labels/emotion names) is translated ko/en. `reply_text`, `letter_text`, `summary` from the backend are always Korean and are never translated or altered.
- Do not render `diary_text` anywhere — only `letter_text` is shown to the user (backend still generates/stores diary_text; that's fine, just unused in the UI).
- No archive/history screens (`GET /diary`, `GET /letter` list/detail are not called).
- No voice/style selection UI — always use `style: "empathetic"` and the server's default TTS voice (omit `voice` field).
- Recording interaction is click-to-toggle (not push-to-talk).
- Ending flow must call `POST /api/v1/session/end` before `POST /api/v1/diary/generate` (server-side `sleep_color` cache reuse — see `services/diary_service.py`).
- Pure logic (reducer, constants, API layer, hooks' non-DOM logic) gets TDD unit tests with Vitest. Components get React Testing Library render/interaction tests. Timer-driven and Web Audio/MediaRecorder-driven hooks are tested with mocked browser APIs and fake timers — no real microphone needed to run the test suite.
- Every task ends with `npm test` passing and, where noted, `npm run build` succeeding.
- Commit after every task from the `moong-care/` repo root (`front-ui/` is a subdirectory of that repo, not its own repo).

---

## File Map

```
moong-care/front-ui/
├── .env.example
├── .gitignore
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── README.md
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── App.test.tsx
    ├── index.css
    ├── setupTests.ts
    ├── constants/
    │   ├── careEmotions.ts / .test.ts
    │   ├── brightness.ts / .test.ts
    │   └── moongFaceOverlay.ts
    ├── i18n/
    │   ├── dict.ts
    │   └── LanguageContext.tsx / .test.tsx
    ├── api/
    │   ├── types.ts
    │   ├── client.ts / .test.ts
    │   ├── voice.ts / .test.ts
    │   ├── tts.ts / .test.ts
    │   ├── session.ts / .test.ts
    │   └── diary.ts / .test.ts
    ├── state/
    │   ├── types.ts
    │   ├── conversationReducer.ts / .test.ts
    │   └── ConversationContext.tsx / .test.tsx
    ├── hooks/
    │   ├── useAudioRecorder.ts / .test.ts
    │   ├── useMicWaveform.ts / .test.ts
    │   └── useTypewriter.ts / .test.ts
    ├── components/
    │   ├── PitchWaveform/PitchWaveform.tsx, barHeights.ts / .test.ts
    │   ├── MoongFace/MoongFace.tsx, useBlinking.ts / .test.ts, useMouthAmplitude.ts / .test.ts, MoongFace.test.tsx
    │   ├── SpeechBubble/SpeechBubble.tsx / .test.tsx
    │   ├── EmotionColorBar/EmotionColorBar.tsx / .test.tsx
    │   ├── EmotionAtmosphere/EmotionAtmosphere.tsx, buildGradientStyle.ts / .test.ts, EmotionAtmosphere.test.tsx
    │   └── LetterCard/LetterCard.tsx / .test.tsx
    └── screens/
        ├── IntroScreen.tsx / .test.tsx
        ├── ConversationScreen.tsx / .test.tsx
        └── EndingScreen.tsx / .test.tsx
```

---

### Task 1: Scaffold the Vite React+TS project

**Files:**
- Create: `moong-care/front-ui/package.json`
- Create: `moong-care/front-ui/tsconfig.json`
- Create: `moong-care/front-ui/tsconfig.node.json`
- Create: `moong-care/front-ui/vite.config.ts`
- Create: `moong-care/front-ui/index.html`
- Create: `moong-care/front-ui/.env.example`
- Create: `moong-care/front-ui/.gitignore`
- Create: `moong-care/front-ui/src/main.tsx`
- Create: `moong-care/front-ui/src/App.tsx`
- Create: `moong-care/front-ui/src/App.test.tsx`
- Create: `moong-care/front-ui/src/index.css`
- Create: `moong-care/front-ui/src/setupTests.ts`
- Modify: `moong-care/.claude/launch.json`

**Interfaces:**
- Produces: `npm test` and `npm run build` commands runnable from `moong-care/front-ui/`. All later tasks assume this scaffold exists.

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "moong-care-front-ui",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "jsdom": "^25.0.1",
    "typescript": "^5.6.3",
    "vite": "^5.4.10",
    "vitest": "^2.1.4"
  }
}
```

- [ ] **Step 2: Write `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: Write `tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Write `vite.config.ts`**

```ts
/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
  },
})
```

- [ ] **Step 5: Write `index.html`**

```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>뭉이 | MoongCare</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Write `.env.example`**

```
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 7: Write `.gitignore`**

```
node_modules
dist
.env
*.local
```

- [ ] **Step 8: Write `src/index.css`**

```css
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Malgun Gothic", "Segoe UI", sans-serif;
  color: #2a2a2a;
}

button {
  font: inherit;
  cursor: pointer;
}
```

- [ ] **Step 9: Write `src/setupTests.ts`**

```ts
import '@testing-library/jest-dom/vitest'
```

- [ ] **Step 10: Write the failing test `src/App.test.tsx`**

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the MoongCare app shell', () => {
    render(<App />)
    expect(screen.getByText('뭉이')).toBeInTheDocument()
  })
})
```

- [ ] **Step 11: Write `src/App.tsx` (minimal, will be replaced in Task 21)**

```tsx
export default function App() {
  return <div>뭉이</div>
}
```

- [ ] **Step 12: Write `src/main.tsx`**

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 13: Install dependencies**

Run (from `moong-care/front-ui/`): `npm install`
Expected: installs without error, creates `node_modules/` and `package-lock.json`.

- [ ] **Step 14: Run tests to verify the scaffold works**

Run: `npm test`
Expected: PASS — 1 test (`App > renders the MoongCare app shell`).

- [ ] **Step 15: Run the production build to verify the toolchain compiles**

Run: `npm run build`
Expected: exits 0, creates `dist/`.

- [ ] **Step 16: Fix `.claude/launch.json` to point at the real front-ui path**

Read the current file at `moong-care/.claude/launch.json` first (it currently points `moong-care-frontend` at a stale `C:\Moong-Care-ver.2` path from a different machine). Replace the `moong-care-frontend` configuration's `runtimeArgs` prefix path with the actual repo-relative front-ui folder:

```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "moong-care-frontend",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["--prefix", "front-ui", "run", "dev"],
      "port": 5173
    },
    {
      "name": "moong-care-server",
      "runtimeExecutable": "C:\\moong-care\\.venv\\Scripts\\python.exe",
      "runtimeArgs": ["main.py"],
      "port": 8000
    }
  ]
}
```

- [ ] **Step 17: Commit**

```bash
git add front-ui .claude/launch.json
git commit -m "chore: scaffold front-ui Vite React+TS project"
```

---

### Task 2: Care-emotion constants + brightness descriptor

**Files:**
- Create: `moong-care/front-ui/src/constants/careEmotions.ts`
- Create: `moong-care/front-ui/src/constants/careEmotions.test.ts`
- Create: `moong-care/front-ui/src/constants/brightness.ts`
- Create: `moong-care/front-ui/src/constants/brightness.test.ts`

**Interfaces:**
- Produces: `CareEmotionCode` type, `getCareEmotionInfo(code: string): CareEmotionInfo`, `describeBrightness(brightness: number, lang: 'ko' | 'en'): string`. Consumed by `EmotionColorBar` (Task 15) and `EndingScreen`/`LetterCard` (Tasks 17, 20).

- [ ] **Step 1: Write the failing test `src/constants/brightness.test.ts`**

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- brightness`
Expected: FAIL — `describeBrightness` is not exported / module not found.

- [ ] **Step 3: Write `src/constants/brightness.ts`**

```ts
export type Lang = 'ko' | 'en'

export function describeBrightness(brightness: number, lang: Lang): string {
  if (brightness >= 0.4) return lang === 'ko' ? '환하게' : 'brightly'
  if (brightness >= 0.3) return lang === 'ko' ? '포근하게' : 'warmly'
  return lang === 'ko' ? '은은하게' : 'softly'
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- brightness`
Expected: PASS — 3 tests.

- [ ] **Step 5: Write the failing test `src/constants/careEmotions.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import { getCareEmotionInfo } from './careEmotions'

describe('getCareEmotionInfo', () => {
  it('returns the known Korean/English labels for a valid code', () => {
    const info = getCareEmotionInfo('sadness')
    expect(info.labelKo).toBe('슬픔')
    expect(info.labelEn).toBe('Sadness')
    expect(info.colorNameKo).toBe('따뜻한 살구빛')
    expect(info.careReasonKo).toBe('따뜻하게 위로')
  })

  it('falls back to calm for an unknown code (matches backend FALLBACK_CARE_EMOTION)', () => {
    const info = getCareEmotionInfo('not_a_real_emotion')
    expect(info.labelKo).toBe('평온')
    expect(info.labelEn).toBe('Calm')
  })
})
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npm test -- careEmotions`
Expected: FAIL — module not found.

- [ ] **Step 7: Write `src/constants/careEmotions.ts`**

```ts
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
```

- [ ] **Step 8: Run test to verify it passes**

Run: `npm test -- careEmotions`
Expected: PASS — 2 tests.

- [ ] **Step 9: Commit**

```bash
git add front-ui/src/constants
git commit -m "feat: add care-emotion labels and brightness descriptor constants"
```

---

### Task 3: i18n dictionary + language context

**Files:**
- Create: `moong-care/front-ui/src/i18n/dict.ts`
- Create: `moong-care/front-ui/src/i18n/LanguageContext.tsx`
- Create: `moong-care/front-ui/src/i18n/LanguageContext.test.tsx`

**Interfaces:**
- Consumes: `Lang` type from `constants/brightness.ts` (Task 2).
- Produces: `LanguageProvider` component, `useTranslation()` hook returning `{ lang, setLang, t(key) }`. Consumed by every screen/component from Task 14 onward.

- [ ] **Step 1: Write `src/i18n/dict.ts`**

```ts
import type { Lang } from '../constants/brightness'

export type DictKey =
  | 'appTitle'
  | 'introGreeting'
  | 'startConversationButton'
  | 'recordStart'
  | 'recordStop'
  | 'thinking'
  | 'endConversationButton'
  | 'newConversationButton'
  | 'yourEmotionLabel'
  | 'colorSuffix'
  | 'micPermissionDenied'
  | 'networkErrorRetry'
  | 'retryButton'
  | 'loadingLetter'
  | 'todaysEmotionLabel'
  | 'languageToggleLabel'
  | 'languageNote'

export const DICT: Record<Lang, Record<DictKey, string>> = {
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
    micPermissionDenied: '마이크 권한이 필요해요. 브라우저 설정에서 허용해줘.',
    networkErrorRetry: '연결에 문제가 생겼어. 다시 시도해줘.',
    retryButton: '다시 시도',
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
    micPermissionDenied: 'Microphone access is needed. Please allow it in your browser settings.',
    networkErrorRetry: 'Something went wrong with the connection. Please try again.',
    retryButton: 'Retry',
    loadingLetter: 'Moong is writing your letter...',
    todaysEmotionLabel: "Today's emotion:",
    languageToggleLabel: '한국어',
    languageNote: "Moong's actual replies are always in Korean.",
  },
}
```

- [ ] **Step 2: Write the failing test `src/i18n/LanguageContext.test.tsx`**

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LanguageProvider, useTranslation } from './LanguageContext'

function Probe() {
  const { lang, setLang, t } = useTranslation()
  return (
    <div>
      <span data-testid="greeting">{t('introGreeting')}</span>
      <span data-testid="lang">{lang}</span>
      <button onClick={() => setLang(lang === 'ko' ? 'en' : 'ko')}>toggle</button>
    </div>
  )
}

describe('LanguageContext', () => {
  it('defaults to Korean and switches to English on demand', () => {
    render(
      <LanguageProvider>
        <Probe />
      </LanguageProvider>,
    )
    expect(screen.getByTestId('lang').textContent).toBe('ko')
    expect(screen.getByTestId('greeting').textContent).toContain('뭉이')

    fireEvent.click(screen.getByText('toggle'))

    expect(screen.getByTestId('lang').textContent).toBe('en')
    expect(screen.getByTestId('greeting').textContent).toContain('Moong')
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm test -- LanguageContext`
Expected: FAIL — module not found.

- [ ] **Step 4: Write `src/i18n/LanguageContext.tsx`**

```tsx
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Lang } from '../constants/brightness'
import { DICT, type DictKey } from './dict'

interface LanguageContextValue {
  lang: Lang
  setLang: (lang: Lang) => void
  t: (key: DictKey) => string
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>('ko')

  const value = useMemo<LanguageContextValue>(
    () => ({
      lang,
      setLang,
      t: (key: DictKey) => DICT[lang][key],
    }),
    [lang],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useTranslation(): LanguageContextValue {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useTranslation must be used within a LanguageProvider')
  return ctx
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test -- LanguageContext`
Expected: PASS — 1 test.

- [ ] **Step 6: Commit**

```bash
git add front-ui/src/i18n
git commit -m "feat: add ko/en language context and UI string dictionary"
```

---

### Task 4: API response types + fetch client wrapper

**Files:**
- Create: `moong-care/front-ui/src/api/types.ts`
- Create: `moong-care/front-ui/src/api/client.ts`
- Create: `moong-care/front-ui/src/api/client.test.ts`

**Interfaces:**
- Produces: `CareColor`, `VoiceAnalyzeResponse`, `SessionEndResponse`, `DiaryGenerateResponse` types (field names match `models/voice.py`, `models/emotion.py`, `models/diary.py`, `models/care.py` exactly); `API_BASE_URL`, `ApiError`, `handleResponse<T>(res: Response): Promise<T>`. Consumed by Tasks 5 and 6.

- [ ] **Step 1: Write `src/api/types.ts`**

```ts
// Mirrors models/care.py CareColor
export interface CareColor {
  hex: string
  brightness: number
  transition_ms: number
}

// Mirrors models/voice.py VoiceAnalyzeResponse
export interface VoiceAnalyzeResponse {
  transcript: string
  emotions: Record<string, number>
  pitch_mean: number
  pitch_std: number
  care_emotion: string
  care_emotion_label: string
  care_confidence: number
  care_color: CareColor
  reply_text: string
}

// Mirrors models/emotion.py SessionEndResponse
export interface SessionEndResponse {
  dominant_emotion: string
  average_emotions: Record<string, number>
  sleep_color: CareColor
}

// Mirrors models/diary.py DiaryGenerateResponse
export interface DiaryGenerateResponse {
  diary_id: number
  letter_id: number
  diary_text: string
  letter_text: string
  summary: string
  dominant_emotion: string
}
```

- [ ] **Step 2: Write the failing test `src/api/client.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import { ApiError, handleResponse } from './client'

describe('handleResponse', () => {
  it('parses JSON body on a 200 response', async () => {
    const res = new Response(JSON.stringify({ a: 1 }), { status: 200 })
    const data = await handleResponse<{ a: number }>(res)
    expect(data.a).toBe(1)
  })

  it('throws ApiError with the status code on a non-2xx response', async () => {
    const res = new Response('session not found', { status: 404, statusText: 'Not Found' })
    const resForSecondRead = res.clone() // Response bodies can only be read once — clone before consuming.
    await expect(handleResponse(res)).rejects.toBeInstanceOf(ApiError)
    try {
      await handleResponse(resForSecondRead)
    } catch (err) {
      expect((err as ApiError).status).toBe(404)
    }
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm test -- client`
Expected: FAIL — module not found.

- [ ] **Step 4: Write `src/api/client.ts`**

```ts
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, text || res.statusText)
  }
  return (await res.json()) as T
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test -- client`
Expected: PASS — 2 tests.

- [ ] **Step 6: Commit**

```bash
git add front-ui/src/api
git commit -m "feat: add API response types and fetch client wrapper"
```

---

### Task 5: `voice/analyze` and `tts` API functions

**Files:**
- Create: `moong-care/front-ui/src/api/voice.ts`
- Create: `moong-care/front-ui/src/api/voice.test.ts`
- Create: `moong-care/front-ui/src/api/tts.ts`
- Create: `moong-care/front-ui/src/api/tts.test.ts`

**Interfaces:**
- Consumes: `API_BASE_URL`, `ApiError`, `handleResponse` from `api/client.ts`; `VoiceAnalyzeResponse` from `api/types.ts` (Task 4).
- Produces: `analyzeVoice(params): Promise<VoiceAnalyzeResponse>`, `synthesizeSpeech(params): Promise<Blob>`. Consumed by `ConversationScreen` (Task 19).

- [ ] **Step 1: Write the failing test `src/api/voice.test.ts`**

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { analyzeVoice } from './voice'

describe('analyzeVoice', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs multipart form data to /api/v1/voice/analyze and returns the parsed response', async () => {
    const mockResponse = {
      transcript: '오늘 좀 힘들었어',
      emotions: { sad: 0.6 },
      pitch_mean: 142.3,
      pitch_std: 18.7,
      care_emotion: 'sadness',
      care_emotion_label: '슬픔',
      care_confidence: 0.81,
      care_color: { hex: '#F2B6A0', brightness: 0.38, transition_ms: 2200 },
      reply_text: '많이 힘들었겠다...',
    }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockResponse), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const audioBlob = new Blob(['fake-audio'], { type: 'audio/webm' })
    const result = await analyzeVoice({ sessionId: 'sess-1', audioBlob })

    expect(result.reply_text).toBe('많이 힘들었겠다...')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/v1/voice/analyze')
    expect(init.method).toBe('POST')
    const body = init.body as FormData
    expect(body.get('session_id')).toBe('sess-1')
    expect(body.get('style')).toBe('empathetic')
    expect(body.get('audio')).toBeInstanceOf(Blob)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- voice`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/api/voice.ts`**

```ts
import { API_BASE_URL, handleResponse } from './client'
import type { VoiceAnalyzeResponse } from './types'

export interface AnalyzeVoiceParams {
  sessionId: string
  audioBlob: Blob
  style?: string
}

export async function analyzeVoice(params: AnalyzeVoiceParams): Promise<VoiceAnalyzeResponse> {
  const form = new FormData()
  form.append('session_id', params.sessionId)
  form.append('style', params.style ?? 'empathetic')
  form.append('audio', params.audioBlob, 'recording.webm')

  const res = await fetch(`${API_BASE_URL}/api/v1/voice/analyze`, {
    method: 'POST',
    body: form,
  })
  return handleResponse<VoiceAnalyzeResponse>(res)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- voice`
Expected: PASS — 1 test.

- [ ] **Step 5: Write the failing test `src/api/tts.test.ts`**

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { synthesizeSpeech } from './tts'
import { ApiError } from './client'

describe('synthesizeSpeech', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs JSON to /api/v1/tts and returns an audio blob', async () => {
    const audioBytes = new Uint8Array([1, 2, 3])
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(audioBytes, { status: 200, headers: { 'Content-Type': 'audio/wav' } }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const blob = await synthesizeSpeech({ text: '안녕', sessionId: 'sess-1' })

    expect(blob).toBeInstanceOf(Blob)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/v1/tts')
    expect(init.method).toBe('POST')
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(init.body)).toEqual({ text: '안녕', session_id: 'sess-1', voice: null })
  })

  it('throws ApiError on a non-2xx response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('bad voice', { status: 400, statusText: 'Bad Request' }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(synthesizeSpeech({ text: '안녕' })).rejects.toBeInstanceOf(ApiError)
  })
})
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npm test -- tts`
Expected: FAIL — module not found.

- [ ] **Step 7: Write `src/api/tts.ts`**

```ts
import { API_BASE_URL, ApiError } from './client'

export interface SynthesizeSpeechParams {
  text: string
  sessionId?: string
  voice?: string
}

export async function synthesizeSpeech(params: SynthesizeSpeechParams): Promise<Blob> {
  const res = await fetch(`${API_BASE_URL}/api/v1/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text: params.text,
      session_id: params.sessionId ?? null,
      voice: params.voice ?? null,
    }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, text || res.statusText)
  }
  return res.blob()
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `npm test -- tts`
Expected: PASS — 2 tests.

- [ ] **Step 9: Commit**

```bash
git add front-ui/src/api
git commit -m "feat: add voice/analyze and tts API functions"
```

---

### Task 6: `session/end` and `diary/generate` API functions

**Files:**
- Create: `moong-care/front-ui/src/api/session.ts`
- Create: `moong-care/front-ui/src/api/session.test.ts`
- Create: `moong-care/front-ui/src/api/diary.ts`
- Create: `moong-care/front-ui/src/api/diary.test.ts`

**Interfaces:**
- Consumes: `API_BASE_URL`, `handleResponse` from `api/client.ts`; `SessionEndResponse`, `DiaryGenerateResponse` from `api/types.ts` (Task 4).
- Produces: `endSession(sessionId): Promise<SessionEndResponse>`, `generateDiary(sessionId): Promise<DiaryGenerateResponse>`. Consumed by `EndingScreen` (Task 20).

- [ ] **Step 1: Write the failing test `src/api/session.test.ts`**

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { endSession } from './session'

describe('endSession', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs { session_id } to /api/v1/session/end and returns the parsed response', async () => {
    const mockResponse = {
      dominant_emotion: 'sadness',
      average_emotions: { sad: 0.55 },
      sleep_color: { hex: '#D18461', brightness: 0.14, transition_ms: 7000 },
    }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockResponse), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await endSession('sess-1')

    expect(result.dominant_emotion).toBe('sadness')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/v1/session/end')
    expect(JSON.parse(init.body)).toEqual({ session_id: 'sess-1' })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- session`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/api/session.ts`**

```ts
import { API_BASE_URL, handleResponse } from './client'
import type { SessionEndResponse } from './types'

export async function endSession(sessionId: string): Promise<SessionEndResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/session/end`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  return handleResponse<SessionEndResponse>(res)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- session`
Expected: PASS — 1 test.

- [ ] **Step 5: Write the failing test `src/api/diary.test.ts`**

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { generateDiary } from './diary'

describe('generateDiary', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs { session_id } to /api/v1/diary/generate and returns the parsed response', async () => {
    const mockResponse = {
      diary_id: 1,
      letter_id: 1,
      diary_text: '오늘은...',
      letter_text: '사랑하는 너에게...',
      summary: '힘든 하루를 보냈지만...',
      dominant_emotion: 'sadness',
    }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockResponse), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await generateDiary('sess-1')

    expect(result.letter_text).toBe('사랑하는 너에게...')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/v1/diary/generate')
    expect(JSON.parse(init.body)).toEqual({ session_id: 'sess-1' })
  })
})
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npm test -- diary`
Expected: FAIL — module not found.

- [ ] **Step 7: Write `src/api/diary.ts`**

```ts
import { API_BASE_URL, handleResponse } from './client'
import type { DiaryGenerateResponse } from './types'

export async function generateDiary(sessionId: string): Promise<DiaryGenerateResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/diary/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  return handleResponse<DiaryGenerateResponse>(res)
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `npm test -- diary`
Expected: PASS — 1 test.

- [ ] **Step 9: Commit**

```bash
git add front-ui/src/api
git commit -m "feat: add session/end and diary/generate API functions"
```

---

### Task 7: Conversation state types + reducer

**Files:**
- Create: `moong-care/front-ui/src/state/types.ts`
- Create: `moong-care/front-ui/src/state/conversationReducer.ts`
- Create: `moong-care/front-ui/src/state/conversationReducer.test.ts`

**Interfaces:**
- Produces: `Screen`, `RecordingStatus`, `TurnResult`, `ConversationState`, `ConversationAction`, `initialConversationState`, `conversationReducer(state, action): ConversationState`. Consumed by `ConversationContext` (Task 8) and all three screens.

- [ ] **Step 1: Write `src/state/types.ts`**

```ts
import type { CareColor } from '../api/types'

export type Screen = 'intro' | 'conversation' | 'ending'
export type RecordingStatus = 'idle' | 'recording' | 'analyzing'
export type EndingStatus = 'idle' | 'loading' | 'done' | 'error'

export interface TurnResult {
  transcript: string
  careEmotion: string
  careEmotionLabel: string
  careColor: CareColor
  pitchMean: number
  pitchStd: number
  replyText: string
}

export interface EndingState {
  status: EndingStatus
  dominantEmotion: string | null
  sleepColor: CareColor | null
  letterText: string | null
  errorMessage: string | null
}

export interface ConversationState {
  screen: Screen
  sessionId: string | null
  recordingStatus: RecordingStatus
  turnCount: number
  currentTurn: TurnResult | null
  turnErrorMessage: string | null
  ending: EndingState
}

export type ConversationAction =
  | { type: 'START_CONVERSATION'; sessionId: string }
  | { type: 'RECORDING_STARTED' }
  | { type: 'RECORDING_STOPPED_ANALYZING' }
  | { type: 'TURN_SUCCESS'; turn: TurnResult }
  | { type: 'TURN_ERROR'; message: string }
  | { type: 'END_REQUESTED' }
  | { type: 'SESSION_ENDED'; dominantEmotion: string; sleepColor: CareColor }
  | { type: 'DIARY_READY'; letterText: string }
  | { type: 'ENDING_ERROR'; message: string }
  | { type: 'RESET' }
```

- [ ] **Step 2: Write the failing test `src/state/conversationReducer.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import { conversationReducer, initialConversationState } from './conversationReducer'
import type { TurnResult } from './types'

const sampleTurn: TurnResult = {
  transcript: '오늘 좀 힘들었어',
  careEmotion: 'sadness',
  careEmotionLabel: '슬픔',
  careColor: { hex: '#F2B6A0', brightness: 0.38, transition_ms: 2200 },
  pitchMean: 142.3,
  pitchStd: 18.7,
  replyText: '많이 힘들었겠다...',
}

describe('conversationReducer', () => {
  it('starts with the intro screen and no session', () => {
    expect(initialConversationState.screen).toBe('intro')
    expect(initialConversationState.sessionId).toBeNull()
  })

  it('START_CONVERSATION moves to the conversation screen with a session id', () => {
    const state = conversationReducer(initialConversationState, {
      type: 'START_CONVERSATION',
      sessionId: 'sess-1',
    })
    expect(state.screen).toBe('conversation')
    expect(state.sessionId).toBe('sess-1')
    expect(state.turnCount).toBe(0)
  })

  it('tracks the recording -> analyzing -> success turn lifecycle', () => {
    let state = conversationReducer(initialConversationState, { type: 'START_CONVERSATION', sessionId: 's' })
    state = conversationReducer(state, { type: 'RECORDING_STARTED' })
    expect(state.recordingStatus).toBe('recording')

    state = conversationReducer(state, { type: 'RECORDING_STOPPED_ANALYZING' })
    expect(state.recordingStatus).toBe('analyzing')

    state = conversationReducer(state, { type: 'TURN_SUCCESS', turn: sampleTurn })
    expect(state.recordingStatus).toBe('idle')
    expect(state.turnCount).toBe(1)
    expect(state.currentTurn).toEqual(sampleTurn)
    expect(state.turnErrorMessage).toBeNull()
  })

  it('TURN_ERROR resets recording status and keeps the turn count unchanged', () => {
    let state = conversationReducer(initialConversationState, { type: 'START_CONVERSATION', sessionId: 's' })
    state = conversationReducer(state, { type: 'TURN_SUCCESS', turn: sampleTurn })
    state = conversationReducer(state, { type: 'TURN_ERROR', message: 'network down' })

    expect(state.recordingStatus).toBe('idle')
    expect(state.turnErrorMessage).toBe('network down')
    expect(state.turnCount).toBe(1)
  })

  it('END_REQUESTED moves to the ending screen in a loading state', () => {
    const state = conversationReducer(initialConversationState, { type: 'END_REQUESTED' })
    expect(state.screen).toBe('ending')
    expect(state.ending.status).toBe('loading')
  })

  it('SESSION_ENDED then DIARY_READY fill in the ending state', () => {
    let state = conversationReducer(initialConversationState, { type: 'END_REQUESTED' })
    state = conversationReducer(state, {
      type: 'SESSION_ENDED',
      dominantEmotion: 'sadness',
      sleepColor: { hex: '#D18461', brightness: 0.14, transition_ms: 7000 },
    })
    expect(state.ending.dominantEmotion).toBe('sadness')
    expect(state.ending.sleepColor?.hex).toBe('#D18461')
    expect(state.ending.status).toBe('loading')

    state = conversationReducer(state, { type: 'DIARY_READY', letterText: '사랑하는 너에게...' })
    expect(state.ending.letterText).toBe('사랑하는 너에게...')
    expect(state.ending.status).toBe('done')
  })

  it('ENDING_ERROR records the error message', () => {
    let state = conversationReducer(initialConversationState, { type: 'END_REQUESTED' })
    state = conversationReducer(state, { type: 'ENDING_ERROR', message: 'session not found' })
    expect(state.ending.status).toBe('error')
    expect(state.ending.errorMessage).toBe('session not found')
  })

  it('RESET returns to the initial state', () => {
    let state = conversationReducer(initialConversationState, { type: 'START_CONVERSATION', sessionId: 's' })
    state = conversationReducer(state, { type: 'RESET' })
    expect(state).toEqual(initialConversationState)
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm test -- conversationReducer`
Expected: FAIL — module not found.

- [ ] **Step 4: Write `src/state/conversationReducer.ts`**

```ts
import type { ConversationAction, ConversationState } from './types'

export const initialConversationState: ConversationState = {
  screen: 'intro',
  sessionId: null,
  recordingStatus: 'idle',
  turnCount: 0,
  currentTurn: null,
  turnErrorMessage: null,
  ending: {
    status: 'idle',
    dominantEmotion: null,
    sleepColor: null,
    letterText: null,
    errorMessage: null,
  },
}

export function conversationReducer(
  state: ConversationState,
  action: ConversationAction,
): ConversationState {
  switch (action.type) {
    case 'START_CONVERSATION':
      return { ...initialConversationState, screen: 'conversation', sessionId: action.sessionId }

    case 'RECORDING_STARTED':
      return { ...state, recordingStatus: 'recording', turnErrorMessage: null }

    case 'RECORDING_STOPPED_ANALYZING':
      return { ...state, recordingStatus: 'analyzing' }

    case 'TURN_SUCCESS':
      return {
        ...state,
        recordingStatus: 'idle',
        turnCount: state.turnCount + 1,
        currentTurn: action.turn,
        turnErrorMessage: null,
      }

    case 'TURN_ERROR':
      return { ...state, recordingStatus: 'idle', turnErrorMessage: action.message }

    case 'END_REQUESTED':
      return {
        ...state,
        screen: 'ending',
        ending: { ...initialConversationState.ending, status: 'loading' },
      }

    case 'SESSION_ENDED':
      return {
        ...state,
        ending: {
          ...state.ending,
          dominantEmotion: action.dominantEmotion,
          sleepColor: action.sleepColor,
        },
      }

    case 'DIARY_READY':
      return {
        ...state,
        ending: { ...state.ending, status: 'done', letterText: action.letterText },
      }

    case 'ENDING_ERROR':
      return {
        ...state,
        ending: { ...state.ending, status: 'error', errorMessage: action.message },
      }

    case 'RESET':
      return initialConversationState

    default:
      return state
  }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test -- conversationReducer`
Expected: PASS — 8 tests.

- [ ] **Step 6: Commit**

```bash
git add front-ui/src/state
git commit -m "feat: add conversation state machine reducer"
```

---

### Task 8: ConversationContext provider

**Files:**
- Create: `moong-care/front-ui/src/state/ConversationContext.tsx`
- Create: `moong-care/front-ui/src/state/ConversationContext.test.tsx`

**Interfaces:**
- Consumes: `conversationReducer`, `initialConversationState` from Task 7.
- Produces: `ConversationProvider`, `useConversation(): { state: ConversationState; dispatch: Dispatch<ConversationAction> }`. Consumed by `App.tsx` (Task 21) and all three screens.

- [ ] **Step 1: Write the failing test `src/state/ConversationContext.test.tsx`**

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ConversationProvider, useConversation } from './ConversationContext'

function Probe() {
  const { state, dispatch } = useConversation()
  return (
    <div>
      <span data-testid="screen">{state.screen}</span>
      <button onClick={() => dispatch({ type: 'START_CONVERSATION', sessionId: 'sess-1' })}>start</button>
    </div>
  )
}

describe('ConversationContext', () => {
  it('provides initial state and dispatches actions through the reducer', () => {
    render(
      <ConversationProvider>
        <Probe />
      </ConversationProvider>,
    )
    expect(screen.getByTestId('screen').textContent).toBe('intro')

    fireEvent.click(screen.getByText('start'))

    expect(screen.getByTestId('screen').textContent).toBe('conversation')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- ConversationContext`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/state/ConversationContext.tsx`**

```tsx
import { createContext, useContext, useReducer, type Dispatch, type ReactNode } from 'react'
import { conversationReducer, initialConversationState } from './conversationReducer'
import type { ConversationAction, ConversationState } from './types'

interface ConversationContextValue {
  state: ConversationState
  dispatch: Dispatch<ConversationAction>
}

const ConversationContext = createContext<ConversationContextValue | null>(null)

export function ConversationProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(conversationReducer, initialConversationState)
  return (
    <ConversationContext.Provider value={{ state, dispatch }}>{children}</ConversationContext.Provider>
  )
}

export function useConversation(): ConversationContextValue {
  const ctx = useContext(ConversationContext)
  if (!ctx) throw new Error('useConversation must be used within a ConversationProvider')
  return ctx
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- ConversationContext`
Expected: PASS — 1 test.

- [ ] **Step 5: Commit**

```bash
git add front-ui/src/state
git commit -m "feat: add ConversationContext provider"
```

---

### Task 9: `useAudioRecorder` hook

**Files:**
- Create: `moong-care/front-ui/src/hooks/useAudioRecorder.ts`
- Create: `moong-care/front-ui/src/hooks/useAudioRecorder.test.ts`

**Interfaces:**
- Produces: `useAudioRecorder(): { isRecording: boolean; error: string | null; stream: MediaStream | null; start(): Promise<void>; stop(): Promise<Blob> }`. Consumed by `ConversationScreen` (Task 19) and `useMicWaveform` (Task 10, via the `stream` it exposes).

- [ ] **Step 1: Write the failing test `src/hooks/useAudioRecorder.test.ts`**

```ts
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAudioRecorder } from './useAudioRecorder'

class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = []
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  state: 'inactive' | 'recording' = 'inactive'

  constructor(public stream: MediaStream) {
    FakeMediaRecorder.instances.push(this)
  }

  start() {
    this.state = 'recording'
  }

  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['chunk'], { type: 'audio/webm' }) })
    this.onstop?.()
  }
}

describe('useAudioRecorder', () => {
  beforeEach(() => {
    FakeMediaRecorder.instances = []
    vi.stubGlobal('MediaRecorder', FakeMediaRecorder as unknown as typeof MediaRecorder)
    vi.stubGlobal('navigator', {
      ...navigator,
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: vi.fn() }],
        } as unknown as MediaStream),
      },
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('starts recording, exposes the stream, and resolves a blob on stop', async () => {
    const { result } = renderHook(() => useAudioRecorder())

    await act(async () => {
      await result.current.start()
    })
    expect(result.current.isRecording).toBe(true)
    expect(result.current.stream).not.toBeNull()

    let blob: Blob | undefined
    await act(async () => {
      blob = await result.current.stop()
    })

    expect(blob).toBeInstanceOf(Blob)
    await waitFor(() => expect(result.current.isRecording).toBe(false))
  })

  it('sets an error message when getUserMedia is denied', async () => {
    vi.stubGlobal('navigator', {
      ...navigator,
      mediaDevices: {
        getUserMedia: vi.fn().mockRejectedValue(new Error('Permission denied')),
      },
    })

    const { result } = renderHook(() => useAudioRecorder())
    await act(async () => {
      await result.current.start()
    })

    expect(result.current.error).toBe('Permission denied')
    expect(result.current.isRecording).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- useAudioRecorder`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/hooks/useAudioRecorder.ts`**

```ts
import { useCallback, useRef, useState } from 'react'

export interface UseAudioRecorderResult {
  isRecording: boolean
  error: string | null
  stream: MediaStream | null
  start: () => Promise<void>
  stop: () => Promise<Blob>
}

export function useAudioRecorder(): UseAudioRecorderResult {
  const [isRecording, setIsRecording] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const start = useCallback(async () => {
    setError(null)
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunksRef.current = []
      const recorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm;codecs=opus' })
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data)
      recorderRef.current = recorder
      setStream(mediaStream)
      recorder.start()
      setIsRecording(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setIsRecording(false)
    }
  }, [])

  const stop = useCallback((): Promise<Blob> => {
    return new Promise((resolve) => {
      const recorder = recorderRef.current
      if (!recorder) {
        resolve(new Blob([], { type: 'audio/webm' }))
        return
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream?.getTracks().forEach((track) => track.stop())
        setStream(null)
        setIsRecording(false)
        resolve(blob)
      }
      recorder.stop()
    })
  }, [stream])

  return { isRecording, error, stream, start, stop }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- useAudioRecorder`
Expected: PASS — 2 tests.

- [ ] **Step 5: Commit**

```bash
git add front-ui/src/hooks/useAudioRecorder.ts front-ui/src/hooks/useAudioRecorder.test.ts
git commit -m "feat: add useAudioRecorder hook"
```

---

### Task 10: `useMicWaveform` hook (live input visualization)

**Files:**
- Create: `moong-care/front-ui/src/hooks/useMicWaveform.ts`
- Create: `moong-care/front-ui/src/hooks/useMicWaveform.test.ts`

**Interfaces:**
- Consumes: a `MediaStream | null` (produced by `useAudioRecorder`, Task 9).
- Produces: `useMicWaveform(stream: MediaStream | null): Uint8Array | null`. Consumed by `PitchWaveform` (Task 11) via `ConversationScreen`.

- [ ] **Step 1: Write the failing test `src/hooks/useMicWaveform.test.ts`**

```ts
import { renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useMicWaveform } from './useMicWaveform'

class FakeAnalyserNode {
  fftSize = 2048
  frequencyBinCount = 1024
  getByteTimeDomainData(arr: Uint8Array) {
    arr.fill(128)
  }
}

class FakeAudioContext {
  createAnalyser() {
    return new FakeAnalyserNode()
  }
  createMediaStreamSource() {
    return { connect: vi.fn() }
  }
  close() {}
}

describe('useMicWaveform', () => {
  beforeEach(() => {
    vi.stubGlobal('AudioContext', FakeAudioContext as unknown as typeof AudioContext)
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0)
      return 1
    })
    vi.stubGlobal('cancelAnimationFrame', () => {})
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns null when there is no stream', () => {
    const { result } = renderHook(() => useMicWaveform(null))
    expect(result.current).toBeNull()
  })

  it('returns sampled waveform data once a stream is provided', () => {
    const fakeStream = {} as MediaStream
    const { result } = renderHook(() => useMicWaveform(fakeStream))
    expect(result.current).not.toBeNull()
    expect(result.current?.length).toBe(1024)
    expect(result.current?.[0]).toBe(128)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- useMicWaveform`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/hooks/useMicWaveform.ts`**

```ts
import { useEffect, useRef, useState } from 'react'

export function useMicWaveform(stream: MediaStream | null): Uint8Array | null {
  const [samples, setSamples] = useState<Uint8Array | null>(null)
  const frameRef = useRef<number | null>(null)

  useEffect(() => {
    if (!stream) {
      setSamples(null)
      return
    }

    const audioContext = new AudioContext()
    const source = audioContext.createMediaStreamSource(stream)
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 2048
    source.connect(analyser)

    const buffer = new Uint8Array(analyser.frequencyBinCount)

    const tick = () => {
      analyser.getByteTimeDomainData(buffer)
      setSamples(new Uint8Array(buffer))
      frameRef.current = requestAnimationFrame(tick)
    }
    tick()

    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
      audioContext.close()
    }
  }, [stream])

  return samples
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- useMicWaveform`
Expected: PASS — 2 tests.

- [ ] **Step 5: Commit**

```bash
git add front-ui/src/hooks/useMicWaveform.ts front-ui/src/hooks/useMicWaveform.test.ts
git commit -m "feat: add useMicWaveform hook for live recording visualization"
```

---

### Task 11: `PitchWaveform` component

**Files:**
- Create: `moong-care/front-ui/src/components/PitchWaveform/barHeights.ts`
- Create: `moong-care/front-ui/src/components/PitchWaveform/barHeights.test.ts`
- Create: `moong-care/front-ui/src/components/PitchWaveform/PitchWaveform.tsx`
- Create: `moong-care/front-ui/src/components/PitchWaveform/PitchWaveform.test.tsx`

**Interfaces:**
- Consumes: `Uint8Array | null` samples (shape produced by `useMicWaveform`, Task 10).
- Produces: `computeBarHeights(samples, barCount): number[]`, `<PitchWaveform samples={...} active={...} />`. Consumed by `ConversationScreen` (Task 19).

- [ ] **Step 1: Write the failing test `src/components/PitchWaveform/barHeights.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import { computeBarHeights } from './barHeights'

describe('computeBarHeights', () => {
  it('returns barCount values normalized to 0-1 from raw byte samples (128 = silence = 0)', () => {
    const samples = new Uint8Array([128, 128, 128, 128])
    const heights = computeBarHeights(samples, 4)
    expect(heights).toEqual([0, 0, 0, 0])
  })

  it('maps max deviation (0 or 255) to 1', () => {
    const samples = new Uint8Array([255, 0, 255, 0])
    const heights = computeBarHeights(samples, 4)
    heights.forEach((h) => expect(h).toBeCloseTo(1, 1))
  })

  it('returns an all-zero array when samples is null', () => {
    expect(computeBarHeights(null, 5)).toEqual([0, 0, 0, 0, 0])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- barHeights`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/components/PitchWaveform/barHeights.ts`**

```ts
export function computeBarHeights(samples: Uint8Array | null, barCount: number): number[] {
  if (!samples || samples.length === 0) return new Array(barCount).fill(0)

  const bucketSize = Math.max(1, Math.floor(samples.length / barCount))
  const heights: number[] = []

  for (let i = 0; i < barCount; i++) {
    const start = i * bucketSize
    const end = Math.min(start + bucketSize, samples.length)
    let maxDeviation = 0
    for (let j = start; j < end; j++) {
      maxDeviation = Math.max(maxDeviation, Math.abs(samples[j] - 128))
    }
    heights.push(Math.min(1, maxDeviation / 128))
  }

  return heights
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- barHeights`
Expected: PASS — 3 tests.

- [ ] **Step 5: Write the failing test `src/components/PitchWaveform/PitchWaveform.test.tsx`**

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PitchWaveform } from './PitchWaveform'

describe('PitchWaveform', () => {
  it('renders a bar for each waveform slot', () => {
    const samples = new Uint8Array(64).fill(200)
    render(<PitchWaveform samples={samples} active barCount={8} />)
    expect(screen.getAllByTestId('waveform-bar')).toHaveLength(8)
  })

  it('renders flat bars when inactive with no samples', () => {
    render(<PitchWaveform samples={null} active={false} barCount={8} />)
    const bars = screen.getAllByTestId('waveform-bar')
    bars.forEach((bar) => expect(bar.style.height).toBe('4%'))
  })
})
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npm test -- PitchWaveform`
Expected: FAIL — module not found.

- [ ] **Step 7: Write `src/components/PitchWaveform/PitchWaveform.tsx`**

```tsx
import { computeBarHeights } from './barHeights'

interface PitchWaveformProps {
  samples: Uint8Array | null
  active: boolean
  barCount?: number
}

const MIN_BAR_HEIGHT_PERCENT = 4

export function PitchWaveform({ samples, active, barCount = 24 }: PitchWaveformProps) {
  const heights = active ? computeBarHeights(samples, barCount) : new Array(barCount).fill(0)

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 48 }}>
      {heights.map((h, i) => (
        <div
          key={i}
          data-testid="waveform-bar"
          style={{
            width: 4,
            height: `${Math.max(MIN_BAR_HEIGHT_PERCENT, h * 100)}%`,
            background: '#8DB7D9',
            borderRadius: 2,
            transition: 'height 60ms linear',
          }}
        />
      ))}
    </div>
  )
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `npm test -- PitchWaveform`
Expected: PASS — 2 tests.

- [ ] **Step 9: Commit**

```bash
git add front-ui/src/components/PitchWaveform
git commit -m "feat: add PitchWaveform live recording visualizer"
```

---

### Task 12: `useBlinking` and `useMouthAmplitude` hooks

**Files:**
- Create: `moong-care/front-ui/src/components/MoongFace/useBlinking.ts`
- Create: `moong-care/front-ui/src/components/MoongFace/useBlinking.test.ts`
- Create: `moong-care/front-ui/src/components/MoongFace/useMouthAmplitude.ts`
- Create: `moong-care/front-ui/src/components/MoongFace/useMouthAmplitude.test.ts`

**Interfaces:**
- Produces: `useBlinking(): boolean` (eyes-open flag), `useMouthAmplitude(audioEl: HTMLAudioElement | null, isPlaying: boolean): number` (0-1 mouth openness). Consumed by `MoongFace` (Task 13).

- [ ] **Step 1: Write the failing test `src/components/MoongFace/useBlinking.test.ts`**

```ts
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useBlinking } from './useBlinking'

describe('useBlinking', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.spyOn(Math, 'random').mockReturnValue(0) // always picks the minimum interval (2000ms)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('starts with eyes open', () => {
    const { result } = renderHook(() => useBlinking())
    expect(result.current).toBe(true)
  })

  it('closes the eyes briefly after the blink interval, then reopens', () => {
    const { result } = renderHook(() => useBlinking())

    act(() => {
      vi.advanceTimersByTime(2000)
    })
    expect(result.current).toBe(false)

    act(() => {
      vi.advanceTimersByTime(150)
    })
    expect(result.current).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- useBlinking`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/components/MoongFace/useBlinking.ts`**

```ts
import { useEffect, useState } from 'react'

const MIN_INTERVAL_MS = 2000
const MAX_INTERVAL_MS = 6000
const BLINK_DURATION_MS = 150

export function useBlinking(): boolean {
  const [eyesOpen, setEyesOpen] = useState(true)

  useEffect(() => {
    let blinkTimeout: ReturnType<typeof setTimeout>

    function scheduleNextBlink() {
      const delay = MIN_INTERVAL_MS + Math.random() * (MAX_INTERVAL_MS - MIN_INTERVAL_MS)
      blinkTimeout = setTimeout(() => {
        setEyesOpen(false)
        blinkTimeout = setTimeout(() => {
          setEyesOpen(true)
          scheduleNextBlink()
        }, BLINK_DURATION_MS)
      }, delay)
    }

    scheduleNextBlink()
    return () => clearTimeout(blinkTimeout)
  }, [])

  return eyesOpen
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- useBlinking`
Expected: PASS — 2 tests.

- [ ] **Step 5: Write the failing test `src/components/MoongFace/useMouthAmplitude.test.ts`**

```ts
import { renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useMouthAmplitude } from './useMouthAmplitude'

class FakeAnalyserNode {
  fftSize = 1024
  frequencyBinCount = 512
  getByteFrequencyData(arr: Uint8Array) {
    arr.fill(200)
  }
}

class FakeAudioContext {
  createAnalyser() {
    return new FakeAnalyserNode()
  }
  createMediaElementSource() {
    return { connect: vi.fn() }
  }
  destination = {}
  close() {}
}

describe('useMouthAmplitude', () => {
  beforeEach(() => {
    vi.stubGlobal('AudioContext', FakeAudioContext as unknown as typeof AudioContext)
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0)
      return 1
    })
    vi.stubGlobal('cancelAnimationFrame', () => {})
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns 0 when not playing', () => {
    const { result } = renderHook(() => useMouthAmplitude(null, false))
    expect(result.current).toBe(0)
  })

  it('returns a normalized amplitude between 0 and 1 while playing', () => {
    const fakeAudioEl = {} as HTMLAudioElement
    const { result } = renderHook(() => useMouthAmplitude(fakeAudioEl, true))
    expect(result.current).toBeGreaterThan(0)
    expect(result.current).toBeLessThanOrEqual(1)
  })
})
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npm test -- useMouthAmplitude`
Expected: FAIL — module not found.

- [ ] **Step 7: Write `src/components/MoongFace/useMouthAmplitude.ts`**

```ts
import { useEffect, useRef, useState } from 'react'

export function useMouthAmplitude(audioEl: HTMLAudioElement | null, isPlaying: boolean): number {
  const [amplitude, setAmplitude] = useState(0)
  const frameRef = useRef<number | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)

  useEffect(() => {
    if (!audioEl || !isPlaying) {
      setAmplitude(0)
      return
    }

    const audioContext = audioContextRef.current ?? new AudioContext()
    audioContextRef.current = audioContext
    const source = audioContext.createMediaElementSource(audioEl)
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 1024
    source.connect(analyser)
    analyser.connect(audioContext.destination)

    const buffer = new Uint8Array(analyser.frequencyBinCount)

    const tick = () => {
      analyser.getByteFrequencyData(buffer)
      const average = buffer.reduce((sum, v) => sum + v, 0) / buffer.length
      setAmplitude(Math.min(1, average / 255))
      frameRef.current = requestAnimationFrame(tick)
    }
    tick()

    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
    }
  }, [audioEl, isPlaying])

  return amplitude
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `npm test -- useMouthAmplitude`
Expected: PASS — 2 tests.

- [ ] **Step 9: Commit**

```bash
git add front-ui/src/components/MoongFace/useBlinking.ts front-ui/src/components/MoongFace/useBlinking.test.ts front-ui/src/components/MoongFace/useMouthAmplitude.ts front-ui/src/components/MoongFace/useMouthAmplitude.test.ts
git commit -m "feat: add MoongFace blinking and mouth-amplitude hooks"
```

---

### Task 13: `MoongFace` component

**Files:**
- Create: `moong-care/front-ui/src/constants/moongFaceOverlay.ts`
- Create: `moong-care/front-ui/src/components/MoongFace/MoongFace.tsx`
- Create: `moong-care/front-ui/src/components/MoongFace/MoongFace.test.tsx`

**Interfaces:**
- Consumes: `useBlinking`, `useMouthAmplitude` (Task 12).
- Produces: `<MoongFace audioElement={...} isSpeaking={...} />`. Consumed by `ConversationScreen` (Task 19).

- [ ] **Step 1: Write `src/constants/moongFaceOverlay.ts`**

```ts
// Percentage-based positions for the eye/mouth overlays on the placeholder
// circular face. When the real illustration is dropped into src/assets/,
// only these coordinates need retuning — no component logic changes.
export const MOONG_FACE_OVERLAY = {
  leftEye: { top: '38%', left: '30%', width: '12%', height: '12%' },
  rightEye: { top: '38%', left: '58%', width: '12%', height: '12%' },
  mouth: { top: '62%', left: '38%', width: '24%', height: '14%' },
}
```

- [ ] **Step 2: Write the failing test `src/components/MoongFace/MoongFace.test.tsx`**

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('./useBlinking', () => ({ useBlinking: () => true }))
vi.mock('./useMouthAmplitude', () => ({ useMouthAmplitude: () => 0.5 }))

import { MoongFace } from './MoongFace'

describe('MoongFace', () => {
  it('renders eye and mouth overlays', () => {
    render(<MoongFace audioElement={null} isSpeaking={false} />)
    expect(screen.getByTestId('moong-left-eye')).toBeInTheDocument()
    expect(screen.getByTestId('moong-right-eye')).toBeInTheDocument()
    expect(screen.getByTestId('moong-mouth')).toBeInTheDocument()
  })

  it('scales the mouth height with the mouth amplitude while speaking', () => {
    render(<MoongFace audioElement={null} isSpeaking />)
    const mouth = screen.getByTestId('moong-mouth')
    // amplitude mocked to 0.5 -> mouth should be taller than its resting state
    expect(mouth.style.transform).toContain('scaleY')
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm test -- MoongFace.test`
Expected: FAIL — module not found.

- [ ] **Step 4: Write `src/components/MoongFace/MoongFace.tsx`**

```tsx
import { MOONG_FACE_OVERLAY } from '../../constants/moongFaceOverlay'
import { useBlinking } from './useBlinking'
import { useMouthAmplitude } from './useMouthAmplitude'

interface MoongFaceProps {
  audioElement: HTMLAudioElement | null
  isSpeaking: boolean
}

export function MoongFace({ audioElement, isSpeaking }: MoongFaceProps) {
  const eyesOpen = useBlinking()
  const mouthAmplitude = useMouthAmplitude(audioElement, isSpeaking)

  const eyeScaleY = eyesOpen ? 1 : 0.08
  const mouthScaleY = 0.35 + mouthAmplitude * 0.65

  return (
    <div
      style={{
        position: 'relative',
        width: 220,
        height: 220,
        borderRadius: '50%',
        background: '#FFF3D9',
        boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
      }}
      aria-label="뭉이"
    >
      <div
        data-testid="moong-left-eye"
        style={{
          position: 'absolute',
          ...MOONG_FACE_OVERLAY.leftEye,
          background: '#3a3a3a',
          borderRadius: '50%',
          transform: `scaleY(${eyeScaleY})`,
          transition: 'transform 80ms ease',
        }}
      />
      <div
        data-testid="moong-right-eye"
        style={{
          position: 'absolute',
          ...MOONG_FACE_OVERLAY.rightEye,
          background: '#3a3a3a',
          borderRadius: '50%',
          transform: `scaleY(${eyeScaleY})`,
          transition: 'transform 80ms ease',
        }}
      />
      <div
        data-testid="moong-mouth"
        style={{
          position: 'absolute',
          ...MOONG_FACE_OVERLAY.mouth,
          background: '#B5544A',
          borderRadius: '0 0 40% 40% / 0 0 100% 100%',
          transform: `scaleY(${mouthScaleY})`,
          transformOrigin: 'top',
          transition: 'transform 60ms linear',
        }}
      />
    </div>
  )
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test -- MoongFace.test`
Expected: PASS — 2 tests.

- [ ] **Step 6: Commit**

```bash
git add front-ui/src/constants/moongFaceOverlay.ts front-ui/src/components/MoongFace/MoongFace.tsx front-ui/src/components/MoongFace/MoongFace.test.tsx
git commit -m "feat: add MoongFace placeholder character with blink/mouth animation"
```

---

### Task 14: `SpeechBubble` component

**Files:**
- Create: `moong-care/front-ui/src/components/SpeechBubble/SpeechBubble.tsx`
- Create: `moong-care/front-ui/src/components/SpeechBubble/SpeechBubble.test.tsx`

**Interfaces:**
- Consumes: `useTranslation` (Task 3).
- Produces: `<SpeechBubble status={'idle'|'thinking'|'reply'} text={string} />`. Consumed by `ConversationScreen` (Task 19).

- [ ] **Step 1: Write the failing test `src/components/SpeechBubble/SpeechBubble.test.tsx`**

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LanguageProvider } from '../../i18n/LanguageContext'
import { SpeechBubble } from './SpeechBubble'

function renderWithLang(ui: React.ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>)
}

describe('SpeechBubble', () => {
  it('renders nothing when idle', () => {
    const { container } = renderWithLang(<SpeechBubble status="idle" />)
    expect(container.textContent).toBe('')
  })

  it('shows a thinking indicator while waiting for a reply', () => {
    renderWithLang(<SpeechBubble status="thinking" />)
    expect(screen.getByText('답변 고민 중')).toBeInTheDocument()
  })

  it('shows the reply text once available', () => {
    renderWithLang(<SpeechBubble status="reply" text="많이 힘들었겠다..." />)
    expect(screen.getByText('많이 힘들었겠다...')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- SpeechBubble`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/components/SpeechBubble/SpeechBubble.tsx`**

```tsx
import { useTranslation } from '../../i18n/LanguageContext'

interface SpeechBubbleProps {
  status: 'idle' | 'thinking' | 'reply'
  text?: string
}

export function SpeechBubble({ status, text }: SpeechBubbleProps) {
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
      {status === 'thinking' ? (
        <span aria-live="polite">{t('thinking')}...</span>
      ) : (
        <span aria-live="polite">{text}</span>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- SpeechBubble`
Expected: PASS — 3 tests.

- [ ] **Step 5: Commit**

```bash
git add front-ui/src/components/SpeechBubble
git commit -m "feat: add SpeechBubble component"
```

---

### Task 15: `EmotionColorBar` component

**Files:**
- Create: `moong-care/front-ui/src/components/EmotionColorBar/EmotionColorBar.tsx`
- Create: `moong-care/front-ui/src/components/EmotionColorBar/EmotionColorBar.test.tsx`

**Interfaces:**
- Consumes: `getCareEmotionInfo`, `describeBrightness` (Task 2), `useTranslation` (Task 3).
- Produces: `<EmotionColorBar careEmotion={string} brightness={number} />`. Consumed by `ConversationScreen` (Task 19).

- [ ] **Step 1: Write the failing test `src/components/EmotionColorBar/EmotionColorBar.test.tsx`**

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LanguageProvider } from '../../i18n/LanguageContext'
import { EmotionColorBar } from './EmotionColorBar'

describe('EmotionColorBar', () => {
  it('shows the Korean emotion label, color name, brightness, and care reason', () => {
    render(
      <LanguageProvider>
        <EmotionColorBar careEmotion="joy" brightness={0.5} />
      </LanguageProvider>,
    )
    expect(screen.getByText(/사용자의 감정:/)).toHaveTextContent('사용자의 감정: 기쁨/만족')
    expect(screen.getByText(/기쁨\/만족의 색상:/)).toHaveTextContent(
      '기쁨/만족의 색상: 따뜻한 골드 (환하게) — 과각성 없이 따뜻하게 유지',
    )
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- EmotionColorBar`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/components/EmotionColorBar/EmotionColorBar.tsx`**

```tsx
import { describeBrightness } from '../../constants/brightness'
import { getCareEmotionInfo } from '../../constants/careEmotions'
import { useTranslation } from '../../i18n/LanguageContext'

interface EmotionColorBarProps {
  careEmotion: string
  brightness: number
}

export function EmotionColorBar({ careEmotion, brightness }: EmotionColorBarProps) {
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- EmotionColorBar`
Expected: PASS — 1 test.

- [ ] **Step 5: Commit**

```bash
git add front-ui/src/components/EmotionColorBar
git commit -m "feat: add EmotionColorBar component"
```

---

### Task 16: `EmotionAtmosphere` component (background gradient)

**Files:**
- Create: `moong-care/front-ui/src/components/EmotionAtmosphere/buildGradientStyle.ts`
- Create: `moong-care/front-ui/src/components/EmotionAtmosphere/buildGradientStyle.test.ts`
- Create: `moong-care/front-ui/src/components/EmotionAtmosphere/EmotionAtmosphere.tsx`
- Create: `moong-care/front-ui/src/components/EmotionAtmosphere/EmotionAtmosphere.test.tsx`

**Interfaces:**
- Consumes: `CareColor` type (Task 4).
- Produces: `buildGradientStyle(color: CareColor | null): CSSProperties`, `<EmotionAtmosphere color={CareColor | null}>{children}</EmotionAtmosphere>`. Consumed by `ConversationScreen` (Task 19) and `EndingScreen` (Task 20).

- [ ] **Step 1: Write the failing test `src/components/EmotionAtmosphere/buildGradientStyle.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import { buildGradientStyle, DEFAULT_ATMOSPHERE_COLOR } from './buildGradientStyle'

describe('buildGradientStyle', () => {
  it('builds a radial gradient background using the given hex and transition duration', () => {
    const style = buildGradientStyle({ hex: '#F2B6A0', brightness: 0.38, transition_ms: 2200 })
    expect(style.background).toContain('#F2B6A0')
    expect(style.transition).toBe('background 2200ms ease')
  })

  it('falls back to the default calm color when color is null', () => {
    const style = buildGradientStyle(null)
    expect(style.background).toContain(DEFAULT_ATMOSPHERE_COLOR.hex)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- buildGradientStyle`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/components/EmotionAtmosphere/buildGradientStyle.ts`**

```ts
import type { CSSProperties } from 'react'
import type { CareColor } from '../../api/types'

// Pre-turn ambience, matches services/color_care_service.py REALTIME_COLORS['calm'].
export const DEFAULT_ATMOSPHERE_COLOR: CareColor = {
  hex: '#A7CDBD',
  brightness: 0.42,
  transition_ms: 1600,
}

export function buildGradientStyle(color: CareColor | null): CSSProperties {
  const resolved = color ?? DEFAULT_ATMOSPHERE_COLOR
  return {
    background: `radial-gradient(circle at 50% 30%, ${resolved.hex}55 0%, ${resolved.hex}22 55%, transparent 100%)`,
    transition: `background ${resolved.transition_ms}ms ease`,
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- buildGradientStyle`
Expected: PASS — 2 tests.

- [ ] **Step 5: Write the failing test `src/components/EmotionAtmosphere/EmotionAtmosphere.test.tsx`**

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EmotionAtmosphere } from './EmotionAtmosphere'

describe('EmotionAtmosphere', () => {
  it('renders children on top of the gradient background', () => {
    render(
      <EmotionAtmosphere color={{ hex: '#F2B6A0', brightness: 0.38, transition_ms: 2200 }}>
        <span>content</span>
      </EmotionAtmosphere>,
    )
    expect(screen.getByText('content')).toBeInTheDocument()
    expect(screen.getByTestId('emotion-atmosphere').style.background).toContain('#F2B6A0')
  })
})
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npm test -- EmotionAtmosphere.test`
Expected: FAIL — module not found.

- [ ] **Step 7: Write `src/components/EmotionAtmosphere/EmotionAtmosphere.tsx`**

```tsx
import type { ReactNode } from 'react'
import type { CareColor } from '../../api/types'
import { buildGradientStyle } from './buildGradientStyle'

interface EmotionAtmosphereProps {
  color: CareColor | null
  children: ReactNode
}

export function EmotionAtmosphere({ color, children }: EmotionAtmosphereProps) {
  return (
    <div
      data-testid="emotion-atmosphere"
      style={{
        minHeight: '100vh',
        width: '100%',
        ...buildGradientStyle(color),
      }}
    >
      {children}
    </div>
  )
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `npm test -- EmotionAtmosphere.test`
Expected: PASS — 1 test.

- [ ] **Step 9: Commit**

```bash
git add front-ui/src/components/EmotionAtmosphere
git commit -m "feat: add EmotionAtmosphere background gradient component"
```

---

### Task 17: `useTypewriter` hook + `LetterCard` component

**Files:**
- Create: `moong-care/front-ui/src/hooks/useTypewriter.ts`
- Create: `moong-care/front-ui/src/hooks/useTypewriter.test.ts`
- Create: `moong-care/front-ui/src/components/LetterCard/LetterCard.tsx`
- Create: `moong-care/front-ui/src/components/LetterCard/LetterCard.test.tsx`

**Interfaces:**
- Produces: `useTypewriter(text: string, speedMs?: number): { displayedText: string; isDone: boolean }`, `<LetterCard dominantEmotionLabel={string} letterText={string} />`. Consumed by `EndingScreen` (Task 20).

- [ ] **Step 1: Write the failing test `src/hooks/useTypewriter.test.ts`**

```ts
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useTypewriter } from './useTypewriter'

describe('useTypewriter', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('reveals the text one character at a time and marks done at the end', () => {
    const { result } = renderHook(() => useTypewriter('안녕', 10))
    expect(result.current.displayedText).toBe('')
    expect(result.current.isDone).toBe(false)

    act(() => {
      vi.advanceTimersByTime(10)
    })
    expect(result.current.displayedText).toBe('안')

    act(() => {
      vi.advanceTimersByTime(10)
    })
    expect(result.current.displayedText).toBe('안녕')
    expect(result.current.isDone).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- useTypewriter`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/hooks/useTypewriter.ts`**

```ts
import { useEffect, useState } from 'react'

export function useTypewriter(text: string, speedMs = 30): { displayedText: string; isDone: boolean } {
  const [charCount, setCharCount] = useState(0)

  useEffect(() => {
    setCharCount(0)
    if (!text) return

    const interval = setInterval(() => {
      setCharCount((count) => {
        if (count >= text.length) {
          clearInterval(interval)
          return count
        }
        return count + 1
      })
    }, speedMs)

    return () => clearInterval(interval)
  }, [text, speedMs])

  return { displayedText: text.slice(0, charCount), isDone: charCount >= text.length }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- useTypewriter`
Expected: PASS — 1 test.

- [ ] **Step 5: Write the failing test `src/components/LetterCard/LetterCard.test.tsx`**

```tsx
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LetterCard } from './LetterCard'

describe('LetterCard', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the emotion tag and reveals the full letter text over time', () => {
    render(<LetterCard dominantEmotionLabel="슬픔" letterText="사랑하는 너에게" />)
    expect(screen.getByText(/오늘의 감정:/)).toHaveTextContent('오늘의 감정: 슬픔')

    act(() => {
      vi.advanceTimersByTime(30 * '사랑하는 너에게'.length)
    })
    expect(screen.getByTestId('letter-body').textContent).toBe('사랑하는 너에게')
  })
})
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npm test -- LetterCard`
Expected: FAIL — module not found.

- [ ] **Step 7: Write `src/components/LetterCard/LetterCard.tsx`**

```tsx
import { useTranslation } from '../../i18n/LanguageContext'
import { useTypewriter } from '../../hooks/useTypewriter'

interface LetterCardProps {
  dominantEmotionLabel: string
  letterText: string
}

export function LetterCard({ dominantEmotionLabel, letterText }: LetterCardProps) {
  const { t } = useTranslation()
  const { displayedText } = useTypewriter(letterText, 30)

  return (
    <div
      style={{
        maxWidth: 480,
        margin: '0 auto',
        padding: '32px 28px',
        background: '#FBF3E3',
        border: '1px solid #E6D8B8',
        borderRadius: 12,
        boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
        fontFamily: 'Georgia, "Malgun Gothic", serif',
      }}
    >
      <div
        style={{
          display: 'inline-block',
          padding: '4px 12px',
          borderRadius: 999,
          background: '#EADFC4',
          fontSize: 12,
          marginBottom: 16,
        }}
      >
        {t('todaysEmotionLabel')} {dominantEmotionLabel}
      </div>
      <p data-testid="letter-body" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7, fontSize: 16 }}>
        {displayedText}
      </p>
    </div>
  )
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `npm test -- LetterCard`
Expected: PASS — 1 test.

- [ ] **Step 9: Commit**

```bash
git add front-ui/src/hooks/useTypewriter.ts front-ui/src/hooks/useTypewriter.test.ts front-ui/src/components/LetterCard
git commit -m "feat: add useTypewriter hook and LetterCard component"
```

---

### Task 18: `IntroScreen`

**Files:**
- Create: `moong-care/front-ui/src/screens/IntroScreen.tsx`
- Create: `moong-care/front-ui/src/screens/IntroScreen.test.tsx`

**Interfaces:**
- Consumes: `useConversation` (Task 8), `useTranslation` (Task 3).
- Produces: `<IntroScreen />`. Consumed by `App.tsx` (Task 21).

- [ ] **Step 1: Write the failing test `src/screens/IntroScreen.test.tsx`**

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LanguageProvider } from '../i18n/LanguageContext'
import { ConversationProvider, useConversation } from '../state/ConversationContext'
import { IntroScreen } from './IntroScreen'

function ScreenProbe() {
  const { state } = useConversation()
  return <div data-testid="probe-screen">{state.screen}</div>
}

describe('IntroScreen', () => {
  it('starts a new conversation with a fresh session id when the button is clicked', () => {
    render(
      <LanguageProvider>
        <ConversationProvider>
          <IntroScreen />
          <ScreenProbe />
        </ConversationProvider>
      </LanguageProvider>,
    )

    expect(screen.getByTestId('probe-screen').textContent).toBe('intro')
    fireEvent.click(screen.getByText('대화 시작'))
    expect(screen.getByTestId('probe-screen').textContent).toBe('conversation')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- IntroScreen`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/screens/IntroScreen.tsx`**

```tsx
import { useTranslation } from '../i18n/LanguageContext'
import { useConversation } from '../state/ConversationContext'

export function IntroScreen() {
  const { t } = useTranslation()
  const { dispatch } = useConversation()

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
      <h1>{t('appTitle')}</h1>
      <p>{t('introGreeting')}</p>
      <button
        style={{ padding: '12px 28px', borderRadius: 999, border: 'none', background: '#A7CDBD', fontSize: 16 }}
        onClick={() => dispatch({ type: 'START_CONVERSATION', sessionId: crypto.randomUUID() })}
      >
        {t('startConversationButton')}
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- IntroScreen`
Expected: PASS — 1 test.

- [ ] **Step 5: Commit**

```bash
git add front-ui/src/screens/IntroScreen.tsx front-ui/src/screens/IntroScreen.test.tsx
git commit -m "feat: add IntroScreen"
```

---

### Task 19: `ConversationScreen` (core turn loop integration)

**Files:**
- Create: `moong-care/front-ui/src/screens/ConversationScreen.tsx`
- Create: `moong-care/front-ui/src/screens/ConversationScreen.test.tsx`

**Interfaces:**
- Consumes: `useConversation` (Task 8), `useAudioRecorder` (Task 9), `useMicWaveform` (Task 10), `PitchWaveform` (Task 11), `MoongFace` (Task 13), `SpeechBubble` (Task 14), `EmotionColorBar` (Task 15), `EmotionAtmosphere` (Task 16), `analyzeVoice` (Task 5), `synthesizeSpeech` (Task 5), `getCareEmotionInfo` (Task 2), `useTranslation` (Task 3).
- Produces: `<ConversationScreen />`. Consumed by `App.tsx` (Task 21).

- [ ] **Step 1: Write the failing test `src/screens/ConversationScreen.test.tsx`**

```tsx
import { act, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../i18n/LanguageContext'
import { ConversationProvider, useConversation } from '../state/ConversationContext'
import { ConversationScreen } from './ConversationScreen'

const mockAnalyzeVoice = vi.fn()
const mockSynthesizeSpeech = vi.fn()
vi.mock('../api/voice', () => ({ analyzeVoice: (...args: unknown[]) => mockAnalyzeVoice(...args) }))
vi.mock('../api/tts', () => ({ synthesizeSpeech: (...args: unknown[]) => mockSynthesizeSpeech(...args) }))

const mockStart = vi.fn().mockResolvedValue(undefined)
const mockStop = vi.fn().mockResolvedValue(new Blob(['audio'], { type: 'audio/webm' }))
// useAudioRecorder itself is a vi.fn() so each test can set its own isRecording value
// (the hook's own start/stop/isRecording *lifecycle* is already covered by Task 9's tests —
// here we only need fixed snapshots of "not recording yet" vs "currently recording").
const mockUseAudioRecorder = vi.fn()
vi.mock('../hooks/useAudioRecorder', () => ({ useAudioRecorder: () => mockUseAudioRecorder() }))
vi.mock('../hooks/useMicWaveform', () => ({ useMicWaveform: () => null }))

function StartConversation() {
  const { dispatch } = useConversation()
  useEffect(() => {
    dispatch({ type: 'START_CONVERSATION', sessionId: 'sess-1' })
  }, [dispatch])
  return null
}

describe('ConversationScreen', () => {
  beforeEach(() => {
    mockAnalyzeVoice.mockReset()
    mockSynthesizeSpeech.mockReset()
    mockStart.mockClear()
    mockStop.mockClear()
    // jsdom has no real audio playback
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)
    URL.createObjectURL = vi.fn().mockReturnValue('blob:mock')
  })

  it('starts recording when the mic button is pressed while idle, and disables the end button pre-turn', async () => {
    mockUseAudioRecorder.mockReturnValue({
      isRecording: false,
      error: null,
      stream: null,
      start: mockStart,
      stop: mockStop,
    })

    render(
      <LanguageProvider>
        <ConversationProvider>
          <StartConversation />
          <ConversationScreen />
        </ConversationProvider>
      </LanguageProvider>,
    )

    expect(screen.getByText('대화 종료')).toBeDisabled()

    await act(async () => {
      screen.getByRole('button', { name: '눌러서 말하기' }).click()
    })
    expect(mockStart).toHaveBeenCalledTimes(1)
  })

  it('stops recording, analyzes the turn, shows the reply, plays TTS, and enables the end button', async () => {
    mockUseAudioRecorder.mockReturnValue({
      isRecording: true,
      error: null,
      stream: null,
      start: mockStart,
      stop: mockStop,
    })
    mockAnalyzeVoice.mockResolvedValue({
      transcript: '오늘 좀 힘들었어',
      emotions: { sad: 0.6 },
      pitch_mean: 142.3,
      pitch_std: 18.7,
      care_emotion: 'sadness',
      care_emotion_label: '슬픔',
      care_confidence: 0.81,
      care_color: { hex: '#F2B6A0', brightness: 0.38, transition_ms: 2200 },
      reply_text: '많이 힘들었겠다...',
    })
    mockSynthesizeSpeech.mockResolvedValue(new Blob(['audio'], { type: 'audio/wav' }))

    render(
      <LanguageProvider>
        <ConversationProvider>
          <StartConversation />
          <ConversationScreen />
        </ConversationProvider>
      </LanguageProvider>,
    )

    await act(async () => {
      screen.getByRole('button', { name: '녹음 종료' }).click()
    })

    await waitFor(() =>
      expect(mockAnalyzeVoice).toHaveBeenCalledWith({ sessionId: 'sess-1', audioBlob: expect.any(Blob) }),
    )
    await waitFor(() => expect(screen.getByText('많이 힘들었겠다...')).toBeInTheDocument())
    await waitFor(() =>
      expect(mockSynthesizeSpeech).toHaveBeenCalledWith({ text: '많이 힘들었겠다...', sessionId: 'sess-1' }),
    )
    await waitFor(() => expect(screen.getByText('대화 종료')).not.toBeDisabled())
    expect(screen.getByText(/사용자의 감정: 슬픔/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- ConversationScreen`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/screens/ConversationScreen.tsx`**

```tsx
import { useEffect, useRef, useState } from 'react'
import { analyzeVoice } from '../api/voice'
import { synthesizeSpeech } from '../api/tts'
import { EmotionAtmosphere } from '../components/EmotionAtmosphere/EmotionAtmosphere'
import { EmotionColorBar } from '../components/EmotionColorBar/EmotionColorBar'
import { MoongFace } from '../components/MoongFace/MoongFace'
import { PitchWaveform } from '../components/PitchWaveform/PitchWaveform'
import { SpeechBubble } from '../components/SpeechBubble/SpeechBubble'
import { useAudioRecorder } from '../hooks/useAudioRecorder'
import { useMicWaveform } from '../hooks/useMicWaveform'
import { useTranslation } from '../i18n/LanguageContext'
import { useConversation } from '../state/ConversationContext'

export function ConversationScreen() {
  const { t } = useTranslation()
  const { state, dispatch } = useConversation()
  const recorder = useAudioRecorder()
  const waveformSamples = useMicWaveform(recorder.stream)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [isSpeaking, setIsSpeaking] = useState(false)

  useEffect(() => {
    if (recorder.error) {
      dispatch({ type: 'TURN_ERROR', message: recorder.error })
    }
  }, [recorder.error, dispatch])

  async function handleMicClick() {
    if (!state.sessionId) return

    if (!recorder.isRecording) {
      dispatch({ type: 'RECORDING_STARTED' })
      await recorder.start()
      return
    }

    const audioBlob = await recorder.stop()
    dispatch({ type: 'RECORDING_STOPPED_ANALYZING' })

    try {
      const response = await analyzeVoice({ sessionId: state.sessionId, audioBlob })
      dispatch({
        type: 'TURN_SUCCESS',
        turn: {
          transcript: response.transcript,
          careEmotion: response.care_emotion,
          careEmotionLabel: response.care_emotion_label,
          careColor: response.care_color,
          pitchMean: response.pitch_mean,
          pitchStd: response.pitch_std,
          replyText: response.reply_text,
        },
      })

      try {
        const audioBlobReply = await synthesizeSpeech({ text: response.reply_text, sessionId: state.sessionId })
        const url = URL.createObjectURL(audioBlobReply)
        if (audioRef.current) {
          audioRef.current.src = url
          setIsSpeaking(true)
          await audioRef.current.play()
        }
      } catch (ttsError) {
        console.warn('TTS playback failed, continuing with text-only reply', ttsError)
      }
    } catch (err) {
      dispatch({ type: 'TURN_ERROR', message: err instanceof Error ? err.message : String(err) })
    }
  }

  function handleAudioEnded() {
    setIsSpeaking(false)
  }

  const bubbleStatus = recorder.isRecording
    ? 'idle'
    : state.recordingStatus === 'analyzing'
      ? 'thinking'
      : state.currentTurn
        ? 'reply'
        : 'idle'

  return (
    <EmotionAtmosphere color={state.currentTurn?.careColor ?? null}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: 24, minHeight: '100vh' }}>
        <button
          onClick={() => dispatch({ type: 'END_REQUESTED' })}
          disabled={state.turnCount === 0}
          style={{ alignSelf: 'flex-end', padding: '8px 16px', borderRadius: 999, border: '1px solid #ccc', background: '#fff' }}
        >
          {t('endConversationButton')}
        </button>

        <SpeechBubble status={bubbleStatus} text={state.currentTurn?.replyText} />

        <MoongFace audioElement={audioRef.current} isSpeaking={isSpeaking} />

        <audio ref={audioRef} onEnded={handleAudioEnded} style={{ display: 'none' }} />

        <PitchWaveform samples={waveformSamples} active={recorder.isRecording} />

        <button
          onClick={handleMicClick}
          disabled={state.recordingStatus === 'analyzing'}
          style={{ padding: '12px 24px', borderRadius: 999, border: 'none', background: recorder.isRecording ? '#e07a5f' : '#8DB7D9', color: '#fff' }}
        >
          {recorder.isRecording ? t('recordStop') : t('recordStart')}
        </button>

        {recorder.error && <p role="alert">{t('micPermissionDenied')}</p>}
        {state.turnErrorMessage && !recorder.error && <p role="alert">{t('networkErrorRetry')}</p>}

        {state.currentTurn && (
          <EmotionColorBar careEmotion={state.currentTurn.careEmotion} brightness={state.currentTurn.careColor.brightness} />
        )}
      </div>
    </EmotionAtmosphere>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- ConversationScreen`
Expected: PASS — 2 tests.

- [ ] **Step 5: Commit**

```bash
git add front-ui/src/screens/ConversationScreen.tsx front-ui/src/screens/ConversationScreen.test.tsx
git commit -m "feat: add ConversationScreen with full turn loop"
```

---

### Task 20: `EndingScreen`

**Files:**
- Create: `moong-care/front-ui/src/screens/EndingScreen.tsx`
- Create: `moong-care/front-ui/src/screens/EndingScreen.test.tsx`

**Interfaces:**
- Consumes: `useConversation` (Task 8), `endSession` (Task 6), `generateDiary` (Task 6), `EmotionAtmosphere` (Task 16), `LetterCard` (Task 17), `getCareEmotionInfo` (Task 2), `useTranslation` (Task 3).
- Produces: `<EndingScreen />`. Consumed by `App.tsx` (Task 21).

- [ ] **Step 1: Write the failing test `src/screens/EndingScreen.test.tsx`**

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../i18n/LanguageContext'
import { ConversationProvider, useConversation } from '../state/ConversationContext'
import { EndingScreen } from './EndingScreen'
import { useEffect } from 'react'

const mockEndSession = vi.fn()
const mockGenerateDiary = vi.fn()
vi.mock('../api/session', () => ({ endSession: (...args: unknown[]) => mockEndSession(...args) }))
vi.mock('../api/diary', () => ({ generateDiary: (...args: unknown[]) => mockGenerateDiary(...args) }))

function StartInEnding() {
  const { dispatch } = useConversation()
  useEffect(() => {
    dispatch({ type: 'START_CONVERSATION', sessionId: 'sess-1' })
    dispatch({ type: 'END_REQUESTED' })
  }, [dispatch])
  return null
}

describe('EndingScreen', () => {
  beforeEach(() => {
    mockEndSession.mockReset()
    mockGenerateDiary.mockReset()
    mockEndSession.mockResolvedValue({
      dominant_emotion: 'sadness',
      average_emotions: { sad: 0.55 },
      sleep_color: { hex: '#D18461', brightness: 0.14, transition_ms: 7000 },
    })
    mockGenerateDiary.mockResolvedValue({
      diary_id: 1,
      letter_id: 1,
      diary_text: '오늘은...',
      letter_text: '사랑하는 너에게...',
      summary: '힘든 하루',
      dominant_emotion: 'sadness',
    })
  })

  it('calls session/end then diary/generate in order and reveals the letter', async () => {
    render(
      <LanguageProvider>
        <ConversationProvider>
          <StartInEnding />
          <EndingScreen />
        </ConversationProvider>
      </LanguageProvider>,
    )

    await waitFor(() => expect(mockEndSession).toHaveBeenCalledWith('sess-1'))
    await waitFor(() => expect(mockGenerateDiary).toHaveBeenCalledWith('sess-1'))
    expect(mockEndSession.mock.invocationCallOrder[0]).toBeLessThan(mockGenerateDiary.mock.invocationCallOrder[0])

    await waitFor(() => expect(screen.getByText('사랑하는 너에게...')).toBeInTheDocument())
    expect(screen.getByText(/오늘의 감정:/)).toHaveTextContent('오늘의 감정: 슬픔')
  })

  it('dispatches RESET when starting a new conversation', async () => {
    render(
      <LanguageProvider>
        <ConversationProvider>
          <StartInEnding />
          <EndingScreen />
        </ConversationProvider>
      </LanguageProvider>,
    )

    await waitFor(() => expect(screen.getByText('사랑하는 너에게...')).toBeInTheDocument())
    screen.getByText('새 대화 시작').click()
    await waitFor(() => expect(screen.queryByText('사랑하는 너에게...')).not.toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- EndingScreen`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `src/screens/EndingScreen.tsx`**

```tsx
import { useEffect } from 'react'
import { generateDiary } from '../api/diary'
import { endSession } from '../api/session'
import { EmotionAtmosphere } from '../components/EmotionAtmosphere/EmotionAtmosphere'
import { LetterCard } from '../components/LetterCard/LetterCard'
import { getCareEmotionInfo } from '../constants/careEmotions'
import { useTranslation } from '../i18n/LanguageContext'
import { useConversation } from '../state/ConversationContext'

export function EndingScreen() {
  const { t, lang } = useTranslation()
  const { state, dispatch } = useConversation()
  const { sessionId, ending } = state

  useEffect(() => {
    if (!sessionId || ending.status !== 'loading' || ending.letterText) return

    let cancelled = false
    ;(async () => {
      try {
        const sessionResult = await endSession(sessionId)
        if (cancelled) return
        dispatch({
          type: 'SESSION_ENDED',
          dominantEmotion: sessionResult.dominant_emotion,
          sleepColor: sessionResult.sleep_color,
        })

        const diaryResult = await generateDiary(sessionId)
        if (cancelled) return
        dispatch({ type: 'DIARY_READY', letterText: diaryResult.letter_text })
      } catch (err) {
        if (!cancelled) {
          dispatch({ type: 'ENDING_ERROR', message: err instanceof Error ? err.message : String(err) })
        }
      }
    })()

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, ending.status])

  const dominantInfo = ending.dominantEmotion ? getCareEmotionInfo(ending.dominantEmotion) : null
  const dominantLabel = dominantInfo ? (lang === 'ko' ? dominantInfo.labelKo : dominantInfo.labelEn) : ''

  return (
    <EmotionAtmosphere color={ending.sleepColor}>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 24, padding: 24 }}>
        {ending.status === 'error' && <p role="alert">{t('networkErrorRetry')}</p>}
        {(ending.status === 'loading' || (ending.status !== 'error' && !ending.letterText)) && <p>{t('loadingLetter')}</p>}
        {ending.letterText && dominantInfo && <LetterCard dominantEmotionLabel={dominantLabel} letterText={ending.letterText} />}
        <button
          onClick={() => dispatch({ type: 'RESET' })}
          style={{ padding: '10px 22px', borderRadius: 999, border: 'none', background: '#A7CDBD' }}
        >
          {t('newConversationButton')}
        </button>
      </div>
    </EmotionAtmosphere>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- EndingScreen`
Expected: PASS — 2 tests.

- [ ] **Step 5: Commit**

```bash
git add front-ui/src/screens/EndingScreen.tsx front-ui/src/screens/EndingScreen.test.tsx
git commit -m "feat: add EndingScreen with session/end -> diary/generate flow"
```

---

### Task 21: Wire up `App.tsx`, language toggle, and final checks

**Files:**
- Modify: `moong-care/front-ui/src/App.tsx`
- Modify: `moong-care/front-ui/src/App.test.tsx`
- Create: `moong-care/front-ui/README.md`

**Interfaces:**
- Consumes: `LanguageProvider`/`useTranslation` (Task 3), `ConversationProvider`/`useConversation` (Task 8), `IntroScreen` (Task 18), `ConversationScreen` (Task 19), `EndingScreen` (Task 20).
- Produces: the final `App` component — no further consumers, this is the root.

- [ ] **Step 1: Update the failing test `src/App.test.tsx`**

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the intro screen by default with a language toggle', () => {
    render(<App />)
    expect(screen.getByText('대화 시작')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'EN' })).toBeInTheDocument()
  })

  it('switches UI chrome to English when the language toggle is clicked, without translating Moong replies', () => {
    render(<App />)
    screen.getByRole('button', { name: 'EN' }).click()
    expect(screen.getByText('Start talking')).toBeInTheDocument()
    expect(screen.getByText(/always in Korean/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- App.test`
Expected: FAIL — current `App.tsx` only renders `뭉이`, no start button or language toggle.

- [ ] **Step 3: Write `src/App.tsx`**

```tsx
import { LanguageProvider, useTranslation } from './i18n/LanguageContext'
import { ConversationProvider, useConversation } from './state/ConversationContext'
import { IntroScreen } from './screens/IntroScreen'
import { ConversationScreen } from './screens/ConversationScreen'
import { EndingScreen } from './screens/EndingScreen'

function LanguageToggle() {
  const { lang, setLang, t } = useTranslation()
  return (
    <div style={{ position: 'fixed', top: 12, right: 12, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, zIndex: 10 }}>
      <button
        onClick={() => setLang(lang === 'ko' ? 'en' : 'ko')}
        style={{ padding: '4px 12px', borderRadius: 999, border: '1px solid #ccc', background: '#fff', fontSize: 12 }}
      >
        {t('languageToggleLabel')}
      </button>
      <span style={{ fontSize: 11, color: '#777', maxWidth: 180, textAlign: 'right' }}>{t('languageNote')}</span>
    </div>
  )
}

function Screens() {
  const { state } = useConversation()
  if (state.screen === 'intro') return <IntroScreen />
  if (state.screen === 'conversation') return <ConversationScreen />
  return <EndingScreen />
}

export default function App() {
  return (
    <LanguageProvider>
      <ConversationProvider>
        <LanguageToggle />
        <Screens />
      </ConversationProvider>
    </LanguageProvider>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- App.test`
Expected: PASS — 2 tests.

- [ ] **Step 5: Run the full test suite**

Run: `npm test`
Expected: PASS — every test file from Tasks 1-21 green.

- [ ] **Step 6: Run the production build**

Run: `npm run build`
Expected: exits 0 with no TypeScript errors.

- [ ] **Step 7: Write `front-ui/README.md`**

```markdown
# MoongCare front-ui

React + TypeScript + Vite web client for the '뭉이' voice-conversation mood-light service.

## Run locally

1. Start the backend first (from `moong-care/`): `.venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000`
2. Copy `.env.example` to `.env` (defaults already point at `http://localhost:8000`).
3. `npm install`
4. `npm run dev` → open `http://localhost:5173`

Microphone access requires a secure context, so `localhost` is required (this is already the case for `npm run dev`).

## Test

```
npm test
```

## Scope

- No diary text is shown (only the letter). No archive/history screens. No voice/style picker.
  See `docs/superpowers/specs/2026-08-29-front-ui-design.md` for the full design rationale.
```

- [ ] **Step 8: Commit**

```bash
git add front-ui/src/App.tsx front-ui/src/App.test.tsx front-ui/README.md
git commit -m "feat: wire up App with screen routing and language toggle"
```

---

## Post-plan manual verification (not automated)

After Task 21, do this manual check once the real backend is reachable and a real microphone is available:

1. Start the backend (`uvicorn main:app --host 0.0.0.0 --port 8000` from `moong-care/`).
2. `npm run dev` in `moong-care/front-ui/`, open `http://localhost:5173`.
3. Click "대화 시작", allow microphone access, record a short sentence, click "녹음 종료".
4. Confirm: "답변 고민 중" appears, then the reply text, then TTS audio plays with the mouth animating, then the background gradient and emotion/color bar update.
5. Do a second turn, confirm the end button is now enabled.
6. Click "대화 종료", confirm the background shifts to the sleep color and the letter card reveals `letter_text` (not `diary_text`).
7. Click "새 대화 시작", confirm it returns to the intro screen with a fresh session id on the next start.

When the real 뭉이 illustration file is provided, replace the placeholder circle in `MoongFace.tsx` with an `<img>` (or CSS `background-image`) and retune `constants/moongFaceOverlay.ts` coordinates to match — no other files need to change.
