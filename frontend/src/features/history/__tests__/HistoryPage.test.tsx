import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { deleteReport, listReports } from '@/lib/api/client'
import { HistoryPage } from '../HistoryPage'

vi.mock('@/lib/api/client', () => ({
  deleteReport: vi.fn(),
  isRequestAbortError: vi.fn(() => false),
  listReports: vi.fn(),
}))

function paginated(items: Array<{ id: string; query: string; created_at: string; competitor_count: number }>, total?: number) {
  return { items, total: total ?? items.length, limit: 20, offset: 0 }
}

describe('HistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('shows deleting state and prevents duplicate delete clicks', async () => {
    vi.mocked(listReports)
      .mockResolvedValueOnce(paginated([
        {
          id: 'report-1',
          query: 'AI meeting notes',
          created_at: new Date().toISOString(),
          competitor_count: 3,
        },
      ]))
      .mockResolvedValueOnce(paginated([]))

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

    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }))

    await waitFor(() => {
      expect(deleteReport).toHaveBeenCalledTimes(1)
    })
    expect(screen.getByRole('button', { name: /deleting report/i })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: /deleting report/i }))
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
    const firstPage = Array.from({ length: 20 }, (_, index) => ({
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
      .mockResolvedValueOnce(paginated(firstPage, 21))
      .mockResolvedValueOnce(paginated(secondPage, 21))
      .mockResolvedValueOnce(paginated(firstPage, 21))

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
      expect.objectContaining({ limit: 20, offset: 0 }),
    )

    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => {
      expect(screen.getByText('Report 21')).toBeInTheDocument()
    })
    expect(vi.mocked(listReports)).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ limit: 20, offset: 20 }),
    )
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: /previous/i }))
    await waitFor(() => {
      expect(screen.getByText('Report 1')).toBeInTheDocument()
    })
    expect(vi.mocked(listReports)).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({ limit: 20, offset: 0 }),
    )
  })

  it('recovers to previous page when next page becomes empty', async () => {
    const firstPage = Array.from({ length: 20 }, (_, index) => ({
      id: `report-${index + 1}`,
      query: `Report ${index + 1}`,
      created_at: new Date().toISOString(),
      competitor_count: 2,
    }))

    vi.mocked(listReports)
      .mockResolvedValueOnce(paginated(firstPage, 21))
      .mockResolvedValueOnce(paginated([], 20))
      .mockResolvedValueOnce(paginated(firstPage, 20))

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
