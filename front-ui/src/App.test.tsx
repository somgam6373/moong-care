import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('network disabled in tests'))))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the MoongCare app shell', () => {
    render(<App />)
    expect(screen.getByText('뭉이')).toBeInTheDocument()
  })
})
