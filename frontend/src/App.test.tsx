import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./pages/HomePage', () => ({
  HomePage: () => <div>HOME PAGE</div>,
}))

vi.mock('./pages/ReportPage', async () => {
  await new Promise(resolve => setTimeout(resolve, 30))
  return {
    ReportPage: () => <div>REPORT PAGE</div>,
  }
})

vi.mock('./pages/HistoryPage', async () => {
  await new Promise(resolve => setTimeout(resolve, 30))
  return {
    HistoryPage: () => <div>HISTORY PAGE</div>,
  }
})

describe('App route loading', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/reports/r-1')
  })

  it('shows route fallback before lazy page resolves', async () => {
    render(<App />)

    expect(screen.getByTestId('route-loading')).toBeInTheDocument()
    expect(await screen.findByText('REPORT PAGE')).toBeInTheDocument()
  })
})
