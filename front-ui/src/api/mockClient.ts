import type { CareColor, DiaryGenerateResponse, SessionEndResponse, SessionLiveResponse, SessionStartResponse } from './types'

interface MockTurn {
  emotion: string
  transcript: string
  reply: string
  color: CareColor
}

// hex/brightness/transition_ms match services/color_care_service.py REALTIME_COLORS
// (== 뭉이 로봇 MoongCare Color Care Palette.pdf) exactly — this mock data must
// never invent its own colors.
const MOCK_TURNS: MockTurn[] = [
  { emotion: 'calm', transcript: '오늘 하루도 무사히 끝났어.', reply: '수고 많았어요. 오늘 하루는 어땠나요?', color: { hex: '#88D1A6', brightness: 0.42, transition_ms: 1600 } },
  { emotion: 'joy', transcript: '오랜만에 친구를 만나서 기분이 좋았어.', reply: '좋은 시간을 보내셨네요! 그 얘기 더 들려주세요.', color: { hex: '#F2C66D', brightness: 0.50, transition_ms: 1200 } },
  { emotion: 'fatigue', transcript: '일이 너무 많아서 좀 지쳐.', reply: '많이 지치셨겠어요. 오늘은 푹 쉬는 게 좋겠어요.', color: { hex: '#B29E62', brightness: 0.30, transition_ms: 2800 } },
  { emotion: 'anxiety', transcript: '내일 발표 때문에 좀 불안해.', reply: '긴장되시는 게 당연해요. 천천히 숨을 쉬어봐요.', color: { hex: '#6369A6', brightness: 0.36, transition_ms: 2000 } },
  { emotion: 'relief', transcript: '드디어 다 끝냈어, 마음이 편해.', reply: '정말 다행이에요. 편안한 마음으로 마무리해봐요.', color: { hex: '#82D98E', brightness: 0.42, transition_ms: 1800 } },
]

let sessionId: string | null = null
let turnIndex = 0

export async function mockStartSession(): Promise<SessionStartResponse> {
  sessionId = `mock-session-${Date.now()}`
  turnIndex = 0
  return { session_id: sessionId }
}

export function mockAdvanceTurn(): void {
  if (!sessionId) return
  turnIndex = Math.min(turnIndex + 1, MOCK_TURNS.length - 1)
}

export async function mockFetchLive(): Promise<SessionLiveResponse> {
  if (!sessionId) {
    return {
      session_id: null,
      has_session: false,
      ended: false,
      turn_count: 0,
      transcript: null,
      care_emotion: null,
      care_confidence: null,
      care_color: null,
      reply_text: null,
    }
  }

  const turn = MOCK_TURNS[turnIndex]

  return {
    session_id: sessionId,
    has_session: true,
    ended: false,
    turn_count: turnIndex + 1,
    transcript: turn.transcript,
    care_emotion: turn.emotion,
    care_confidence: 0.85,
    care_color: turn.color,
    reply_text: turn.reply,
  }
}

export async function mockEndSession(_sessionId: string): Promise<SessionEndResponse> {
  sessionId = null
  return {
    dominant_emotion: 'calm',
    average_emotions: { calm: 0.4, joy: 0.25, fatigue: 0.15, anxiety: 0.1, relief: 0.1 },
    sleep_color: { hex: '#B86E49', brightness: 0.16, transition_ms: 6000 }, // warm_dim, matches color_care_service.py SLEEP_COLORS
  }
}

export async function mockGenerateDiary(_sessionId: string): Promise<DiaryGenerateResponse> {
  return {
    diary_id: 1,
    letter_id: 1,
    diary_text: '오늘은 이런저런 감정을 겪은 하루였어요. 지치기도 했지만 편안함도 느꼈던 것 같아요.',
    letter_text: '오늘 하루도 정말 고생 많았어요. 지치는 순간도 있었지만, 그 안에서도 편안함을 찾아낸 당신이 대견해요. 내일은 조금 더 가벼운 마음으로 시작할 수 있길 바라요.',
    letter_text_en: "You worked so hard today. There were tiring moments, but I'm proud of you for finding comfort even then. I hope tomorrow starts a little lighter.",
    summary: '지침과 편안함이 섞인 하루',
    dominant_emotion: 'calm',
  }
}
