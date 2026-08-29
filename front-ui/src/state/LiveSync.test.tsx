import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { ConversationProvider, useConversation } from './ConversationContext'
import { LiveSync } from './LiveSync'

function ScreenProbe() {
  const { state } = useConversation()
  return <div data-testid="screen">{state.screen}</div>
}

function renderApp() {
  return render(
    <ConversationProvider>
      <LiveSync />
      <ScreenProbe />
    </ConversationProvider>,
  )
}

describe('LiveSync', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('moves from intro to conversation once a session becomes active', async () => {
    vi.spyOn(client, 'fetchLive').mockResolvedValue({
      session_id: 's1', has_session: true, ended: false, turn_count: 0,
      transcript: null, care_emotion: null, care_confidence: null, care_color: null, reply_text: null,
    })

    renderApp()
    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.getByTestId('screen').textContent).toBe('conversation')
  })

  it('moves to ending once the current session reports ended', async () => {
    vi.spyOn(client, 'fetchLive').mockResolvedValue({
      session_id: 's1', has_session: true, ended: false, turn_count: 0,
      transcript: null, care_emotion: null, care_confidence: null, care_color: null, reply_text: null,
    })
    renderApp()
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByTestId('screen').textContent).toBe('conversation')

    vi.spyOn(client, 'fetchLive').mockResolvedValue({
      session_id: 's1', has_session: true, ended: true, turn_count: 1,
      transcript: '안녕', care_emotion: 'joy', care_confidence: 0.8,
      care_color: { hex: '#F6C66D', brightness: 0.5, transition_ms: 1200 }, reply_text: '반가워!',
    })
    await act(async () => {
      vi.advanceTimersByTime(1500)
      await Promise.resolve()
    })

    expect(screen.getByTestId('screen').textContent).toBe('ending')
  })

  it('moves to ending when the session pointer disappears (end() already cleared it)', async () => {
    vi.spyOn(client, 'fetchLive').mockResolvedValue({
      session_id: 's1', has_session: true, ended: false, turn_count: 0,
      transcript: null, care_emotion: null, care_confidence: null, care_color: null, reply_text: null,
    })
    renderApp()
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByTestId('screen').textContent).toBe('conversation')

    vi.spyOn(client, 'fetchLive').mockResolvedValue({
      session_id: null, has_session: false, ended: false, turn_count: 0,
      transcript: null, care_emotion: null, care_confidence: null, care_color: null, reply_text: null,
    })
    await act(async () => {
      vi.advanceTimersByTime(1500)
      await Promise.resolve()
    })

    expect(screen.getByTestId('screen').textContent).toBe('ending')
  })
})
