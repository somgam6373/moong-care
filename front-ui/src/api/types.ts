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
