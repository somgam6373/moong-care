import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the MoongCare app shell', () => {
    render(<App />)
    expect(screen.getByText('뭉이')).toBeInTheDocument()
  })
})
