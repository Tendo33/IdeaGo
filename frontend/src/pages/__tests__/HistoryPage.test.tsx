import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { deleteReport, listReports } from '../../api/client'
import { HistoryPage } from '../HistoryPage'

vi.mock('../../api/client', () => ({
  deleteReport: vi.fn(),
  isRequestAbortError: vi.fn(() => false),
  listReports: vi.fn(),
}))

describe('HistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('shows deleting state and prevents duplicate delete clicks', async () => {
    vi.mocked(listReports).mockResolvedValue([
      {
        id: 'report-1',
        query: 'AI meeting notes',
        created_at: new Date().toISOString(),
        competitor_count: 3,
      },
    ])

    let resolveDelete: (() => void) | null = null
    vi.mocked(deleteReport).mockImplementation(() => new Promise<void>(resolve => {
      resolveDelete = resolve
    }))

    render(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports/:id" element={<div>REPORT PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('AI meeting notes')).toBeInTheDocument()
    })

    const deleteButton = screen.getByRole('button', { name: /delete report/i })
    fireEvent.click(deleteButton)

    expect(deleteReport).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: /deleting/i })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: /deleting/i }))
    expect(deleteReport).toHaveBeenCalledTimes(1)

    await act(async () => {
      resolveDelete?.()
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(screen.queryByText('AI meeting notes')).not.toBeInTheDocument()
    })
  })
})
