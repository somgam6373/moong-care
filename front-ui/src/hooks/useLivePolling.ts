import { useEffect, useState } from 'react'
import { fetchLive } from '../api/client'
import type { SessionLiveResponse } from '../api/types'

const POLL_INTERVAL_MS = 1500

export interface LivePollingState {
  data: SessionLiveResponse | null
  consecutiveFailures: number
}

export function useLivePolling(): LivePollingState {
  const [state, setState] = useState<LivePollingState>({ data: null, consecutiveFailures: 0 })

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const result = await fetchLive()
        if (cancelled) return
        setState({ data: result, consecutiveFailures: 0 })
      } catch {
        if (cancelled) return
        setState((prev) => ({ data: prev.data, consecutiveFailures: prev.consecutiveFailures + 1 }))
      }
    }

    poll()
    const id = setInterval(poll, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return state
}
