import { createContext, useContext, useReducer, type Dispatch, type ReactNode } from 'react'
import type { CareColor } from '../api/types'

export type Screen = 'intro' | 'conversation' | 'ending'
export type RecordingStatus = 'idle' | 'recording' | 'analyzing'
export type EndingStatus = 'idle' | 'loading' | 'done' | 'error'

export interface TurnResult {
  transcript: string
  careEmotion: string
  careColor: CareColor
  replyText: string
}

export interface EndingState {
  status: EndingStatus
  dominantEmotion: string | null
  sleepColor: CareColor | null
  letterText: string | null
  errorMessage: string | null
}

export interface ConversationState {
  screen: Screen
  sessionId: string | null
  recordingStatus: RecordingStatus
  turnCount: number
  currentTurn: TurnResult | null
  turnErrorMessage: string | null
  ending: EndingState
}

export type ConversationAction =
  | { type: 'START_CONVERSATION'; sessionId: string }
  | { type: 'RECORDING_STARTED' }
  | { type: 'RECORDING_STOPPED_ANALYZING' }
  | { type: 'TURN_SUCCESS'; turn: TurnResult }
  | { type: 'TURN_ERROR'; message: string }
  | { type: 'END_REQUESTED' }
  | { type: 'SESSION_ENDED'; dominantEmotion: string; sleepColor: CareColor }
  | { type: 'DIARY_READY'; letterText: string }
  | { type: 'ENDING_ERROR'; message: string }
  | { type: 'RESET' }

export const initialConversationState: ConversationState = {
  screen: 'intro',
  sessionId: null,
  recordingStatus: 'idle',
  turnCount: 0,
  currentTurn: null,
  turnErrorMessage: null,
  ending: { status: 'idle', dominantEmotion: null, sleepColor: null, letterText: null, errorMessage: null },
}

export function conversationReducer(state: ConversationState, action: ConversationAction): ConversationState {
  switch (action.type) {
    case 'START_CONVERSATION':
      return { ...initialConversationState, screen: 'conversation', sessionId: action.sessionId }
    case 'RECORDING_STARTED':
      return { ...state, recordingStatus: 'recording', turnErrorMessage: null }
    case 'RECORDING_STOPPED_ANALYZING':
      return { ...state, recordingStatus: 'analyzing' }
    case 'TURN_SUCCESS':
      return {
        ...state,
        recordingStatus: 'idle',
        turnCount: state.turnCount + 1,
        currentTurn: action.turn,
        turnErrorMessage: null,
      }
    case 'TURN_ERROR':
      return { ...state, recordingStatus: 'idle', turnErrorMessage: action.message }
    case 'END_REQUESTED':
      return { ...state, screen: 'ending', ending: { ...initialConversationState.ending, status: 'loading' } }
    case 'SESSION_ENDED':
      return {
        ...state,
        ending: { ...state.ending, dominantEmotion: action.dominantEmotion, sleepColor: action.sleepColor },
      }
    case 'DIARY_READY':
      return { ...state, ending: { ...state.ending, status: 'done', letterText: action.letterText } }
    case 'ENDING_ERROR':
      return { ...state, ending: { ...state.ending, status: 'error', errorMessage: action.message } }
    case 'RESET':
      return initialConversationState
    default:
      return state
  }
}

interface ConversationContextValue {
  state: ConversationState
  dispatch: Dispatch<ConversationAction>
}

const ConversationContext = createContext<ConversationContextValue | null>(null)

export function ConversationProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(conversationReducer, initialConversationState)
  return <ConversationContext.Provider value={{ state, dispatch }}>{children}</ConversationContext.Provider>
}

export function useConversation(): ConversationContextValue {
  const ctx = useContext(ConversationContext)
  if (!ctx) throw new Error('useConversation must be used within a ConversationProvider')
  return ctx
}
