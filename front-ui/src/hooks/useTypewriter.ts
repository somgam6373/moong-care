import { useEffect, useState } from 'react'

export function useTypewriter(text: string, speedMs = 30): { displayedText: string; isDone: boolean } {
  const [charCount, setCharCount] = useState(0)

  useEffect(() => {
    setCharCount(0)
    if (!text) return
    const interval = setInterval(() => {
      setCharCount((count) => {
        if (count >= text.length) {
          clearInterval(interval)
          return count
        }
        return count + 1
      })
    }, speedMs)
    return () => clearInterval(interval)
  }, [text, speedMs])

  return { displayedText: text.slice(0, charCount), isDone: charCount >= text.length }
}
