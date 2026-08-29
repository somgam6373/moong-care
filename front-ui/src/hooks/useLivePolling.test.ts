import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { useLivePolling } from './useLivePolling'

const sample = {
  session_id: 's1', has_session: true, ended: false, turn_count: 1,
  transcript: '안녕', care_emotion: 'joy', care_confidence: 0.8,
  care_color: { hex: '#F6C66D', brightness: 0.5, transition_ms: 1200 },
  reply_text: '반가워!',
}

describe('useLivePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('fetches immediately on mount and stores the result', async () => {
    vi.spyOn(client, 'fetchLive').mockResolvedValue(sample)

    const { result } = renderHook(() => useLivePolling())
    await act(async () => {
      await Promise.resolve()
    })

    expect(result.current.data).toEqual(sample)
    expect(result.current.consecutiveFailures).toBe(0)
  })

  it('counts consecutive failures without discarding the last good data', async () => {
    vi.spyOn(client, 'fetchLive').mockResolvedValueOnce(sample).mockRejectedValue(new Error('network error'))

    const { result } = renderHook(() => useLivePolling())
    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current.data).toEqual(sample)

    await act(async () => {
      vi.advanceTimersByTime(1500)
      await Promise.resolve()
    })
    expect(result.current.consecutiveFailures).toBe(1)
    expect(result.current.data).toEqual(sample)

    await act(async () => {
      vi.advanceTimersByTime(1500)
      await Promise.resolve()
    })
    expect(result.current.consecutiveFailures).toBe(2)
  })
})
