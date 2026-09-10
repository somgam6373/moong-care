import { useEffect, useRef } from 'react'
import { useLivePolling } from '../hooks/useLivePolling'
import { useConversation } from './ConversationContext'

export function useLiveSync(): void {
  const live = useLivePolling()
  const { state, dispatch } = useConversation()
  // Tracks the last session_id a live poll actually confirmed (i.e. returned matching
  // has_session/session_id for). Lets us tell "stale poll from before this session
  // started" apart from "this session's pointer just disappeared because it ended" —
  // both show up as session_id !== state.sessionId, but only the latter is real once
  // we've already seen this session confirmed at least once.
  const confirmedSessionRef = useRef<string | null>(null)

  useEffect(() => {
    dispatch({ type: 'CONNECTION_ISSUE', hasIssue: live.consecutiveFailures >= 3 })
  }, [live.consecutiveFailures, dispatch])

  useEffect(() => {
    const data = live.data
    if (!data) return

    if (state.screen === 'intro') {
      if (data.has_session && data.session_id) {
        confirmedSessionRef.current = data.session_id
        dispatch({ type: 'START_CONVERSATION', sessionId: data.session_id })
      }
      return
    }

    if (state.screen === 'conversation') {
      const matchesCurrent = data.session_id === state.sessionId
      if (matchesCurrent) {
        confirmedSessionRef.current = state.sessionId
      } else if (confirmedSessionRef.current !== state.sessionId) {
        // Never confirmed this session via a poll yet — this mismatch is a stale
        // pre-START_CONVERSATION snapshot, not evidence the session ended.
        return
      }

      const stillOngoing = matchesCurrent && data.has_session && !data.ended
      if (!stillOngoing) {
        dispatch({ type: 'END_REQUESTED' })
        return
      }
      if (data.transcript && data.care_emotion && data.care_color && data.reply_text) {
        dispatch({
          type: 'LIVE_TURN',
          turn: {
            transcript: data.transcript,
            careEmotion: data.care_emotion,
            careColor: data.care_color,
            replyText: data.reply_text,
          },
        })
      }
    }
  }, [live.data, state.screen, state.sessionId, dispatch])
}

export function LiveSync() {
  useLiveSync()
  return null
}
