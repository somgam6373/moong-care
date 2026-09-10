// Mirrors models/care.py CareColor
export interface CareColor {
  hex: string
  brightness: number
  transition_ms: number
}

// Mirrors models/emotion.py SessionStartResponse
export interface SessionStartResponse {
  session_id: string
}

// Mirrors models/emotion.py SessionLiveResponse
export interface SessionLiveResponse {
  session_id: string | null
  has_session: boolean
  ended: boolean
  turn_count: number
  transcript: string | null
  care_emotion: string | null
  care_confidence: number | null
  care_color: CareColor | null
  reply_text: string | null
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
  letter_text_en: string
  summary: string
  dominant_emotion: string
}
