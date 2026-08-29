import type { CareColor, DiaryGenerateResponse, SessionEndResponse, SessionLiveResponse, SessionStartResponse } from './types'

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

export async function startSession(): Promise<SessionStartResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/session/start`, { method: 'POST' })
  return handleResponse<SessionStartResponse>(res)
}

export async function fetchLive(): Promise<SessionLiveResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/session/live`)
  return handleResponse<SessionLiveResponse>(res)
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
