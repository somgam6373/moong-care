import { describe, expect, it } from 'vitest'
import { conversationReducer, initialConversationState, type ConversationState } from './ConversationContext'

const color = { hex: '#F6C66D', brightness: 0.5, transition_ms: 1200 }

describe('conversationReducer', () => {
  it('START_CONVERSATION resets state, sets the session, and clears connectionIssue', () => {
    const dirty: ConversationState = { ...initialConversationState, connectionIssue: true }
    const next = conversationReducer(dirty, { type: 'START_CONVERSATION', sessionId: 's1' })
    expect(next.screen).toBe('conversation')
    expect(next.sessionId).toBe('s1')
    expect(next.connectionIssue).toBe(false)
  })

  it('LIVE_TURN updates the current turn without changing the screen', () => {
    const state: ConversationState = { ...initialConversationState, screen: 'conversation', sessionId: 's1' }
    const turn = { transcript: '안녕', careEmotion: 'joy', careColor: color, replyText: '반가워!' }
    const next = conversationReducer(state, { type: 'LIVE_TURN', turn })
    expect(next.currentTurn).toEqual(turn)
    expect(next.screen).toBe('conversation')
  })

  it('CONNECTION_ISSUE sets the flag', () => {
    const next = conversationReducer(initialConversationState, { type: 'CONNECTION_ISSUE', hasIssue: true })
    expect(next.connectionIssue).toBe(true)
  })

  it('END_REQUESTED moves to the ending screen in a loading state', () => {
    const state: ConversationState = { ...initialConversationState, screen: 'conversation', sessionId: 's1' }
    const next = conversationReducer(state, { type: 'END_REQUESTED' })
    expect(next.screen).toBe('ending')
    expect(next.ending.status).toBe('loading')
  })

  it('RESET returns to the initial state', () => {
    const state: ConversationState = { ...initialConversationState, screen: 'ending', sessionId: 's1', connectionIssue: true }
    expect(conversationReducer(state, { type: 'RESET' })).toEqual(initialConversationState)
  })
})
