import { useEffect } from 'react'
import { useLivePolling } from '../hooks/useLivePolling'
import { useConversation } from './ConversationContext'

export function useLiveSync(): void {
  const live = useLivePolling()
  const { state, dispatch } = useConversation()

  useEffect(() => {
    dispatch({ type: 'CONNECTION_ISSUE', hasIssue: live.consecutiveFailures >= 3 })
  }, [live.consecutiveFailures, dispatch])

  useEffect(() => {
    const data = live.data
    if (!data) return

    if (state.screen === 'intro') {
      if (data.has_session && data.session_id) {
        dispatch({ type: 'START_CONVERSATION', sessionId: data.session_id })
      }
      return
    }

    if (state.screen === 'conversation') {
      // A poll started before this session began can resolve after START_CONVERSATION already
      // switched the screen, delivering a stale "no session" snapshot for a different session_id.
      // Ignore it instead of treating it as this session ending.
      if (data.session_id !== state.sessionId) return

      const stillOngoing = data.has_session && !data.ended
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
