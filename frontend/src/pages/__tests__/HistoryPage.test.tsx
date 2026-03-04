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
    vi.mocked(listReports)
      .mockResolvedValueOnce([
        {
          id: 'report-1',
          query: 'AI meeting notes',
          created_at: new Date().toISOString(),
          competitor_count: 3,
        },
      ])
      .mockResolvedValueOnce([])

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

  it('requests paginated report pages and supports page navigation', async () => {
    const firstPageWithSentinel = Array.from({ length: 21 }, (_, index) => ({
      id: `report-${index + 1}`,
      query: `Report ${index + 1}`,
      created_at: new Date().toISOString(),
      competitor_count: 2,
    }))
    const secondPage = [
      {
        id: 'report-21',
        query: 'Report 21',
        created_at: new Date().toISOString(),
        competitor_count: 1,
      },
    ]

    vi.mocked(listReports)
      .mockResolvedValueOnce(firstPageWithSentinel)
      .mockResolvedValueOnce(secondPage)
      .mockResolvedValueOnce(firstPageWithSentinel)

    render(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports/:id" element={<div>REPORT PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Report 1')).toBeInTheDocument()
    })
    expect(vi.mocked(listReports)).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ limit: 21, offset: 0 }),
    )
    expect(screen.queryByText('Report 21')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => {
      expect(screen.getByText('Report 21')).toBeInTheDocument()
    })
    expect(vi.mocked(listReports)).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ limit: 21, offset: 20 }),
    )
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: /previous/i }))
    await waitFor(() => {
      expect(screen.getByText('Report 1')).toBeInTheDocument()
    })
    expect(vi.mocked(listReports)).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({ limit: 21, offset: 0 }),
    )
  })

  it('recovers to previous page when next page becomes empty', async () => {
    const firstPageWithSentinel = Array.from({ length: 21 }, (_, index) => ({
      id: `report-${index + 1}`,
      query: `Report ${index + 1}`,
      created_at: new Date().toISOString(),
      competitor_count: 2,
    }))

    vi.mocked(listReports)
      .mockResolvedValueOnce(firstPageWithSentinel)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce(firstPageWithSentinel)

    render(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports/:id" element={<div>REPORT PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Report 1')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /next/i }))

    await waitFor(() => {
      expect(vi.mocked(listReports)).toHaveBeenCalledTimes(3)
      expect(screen.getByText('Report 1')).toBeInTheDocument()
    })
    expect(screen.queryByText('Report 21')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled()
  })
})
