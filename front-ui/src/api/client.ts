import type { CareColor, DiaryGenerateResponse, SessionEndResponse, SessionLiveResponse, SessionStartResponse } from './types'
import { mockAdvanceTurn, mockEndSession, mockFetchLive, mockGenerateDiary, mockStartSession } from './mockClient'

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
export const USE_MOCK: boolean = import.meta.env.VITE_USE_MOCK === 'true'

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
  if (USE_MOCK) return mockStartSession()
  const res = await fetch(`${API_BASE_URL}/api/v1/session/start`, { method: 'POST' })
  return handleResponse<SessionStartResponse>(res)
}

export async function fetchLive(): Promise<SessionLiveResponse> {
  if (USE_MOCK) return mockFetchLive()
  const res = await fetch(`${API_BASE_URL}/api/v1/session/live`)
  return handleResponse<SessionLiveResponse>(res)
}

// Mock-only: lets the UI advance the canned conversation on click instead of waiting for a real reply.
export function advanceMockTurn(): void {
  if (USE_MOCK) mockAdvanceTurn()
}

export async function endSession(sessionId: string): Promise<SessionEndResponse> {
  if (USE_MOCK) return mockEndSession(sessionId)
  const res = await fetch(`${API_BASE_URL}/api/v1/session/end`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  return handleResponse<SessionEndResponse>(res)
}

export async function generateDiary(sessionId: string): Promise<DiaryGenerateResponse> {
  if (USE_MOCK) return mockGenerateDiary(sessionId)
  const res = await fetch(`${API_BASE_URL}/api/v1/diary/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  return handleResponse<DiaryGenerateResponse>(res)
}

export type { CareColor }
