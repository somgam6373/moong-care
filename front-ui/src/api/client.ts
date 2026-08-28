import type { CareColor, DiaryGenerateResponse, SessionEndResponse, VoiceAnalyzeResponse } from './types'

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, text || res.statusText)
  }
  return (await res.json()) as T
}

export async function analyzeVoice(params: {
  sessionId: string
  audioBlob: Blob
  style?: string
}): Promise<VoiceAnalyzeResponse> {
  const form = new FormData()
  form.append('session_id', params.sessionId)
  form.append('style', params.style ?? 'empathetic')
  form.append('audio', params.audioBlob, 'recording.webm')

  const res = await fetch(`${API_BASE_URL}/api/v1/voice/analyze`, { method: 'POST', body: form })
  return handleResponse<VoiceAnalyzeResponse>(res)
}

export async function synthesizeSpeech(params: {
  text: string
  sessionId?: string
  voice?: string
}): Promise<Blob> {
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

export async function endSession(sessionId: string): Promise<SessionEndResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/session/end`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  return handleResponse<SessionEndResponse>(res)
}

export async function generateDiary(sessionId: string): Promise<DiaryGenerateResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/diary/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  return handleResponse<DiaryGenerateResponse>(res)
}

export type { CareColor }
