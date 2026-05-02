import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { deleteReport, listReports } from '@/lib/api/client'
import { HistoryPage } from '../HistoryPage'

const HISTORY_CACHE_STORAGE_KEY = 'ideago-history-cache'

vi.mock('@/lib/api/client', () => ({
  deleteReport: vi.fn(),
  isRequestAbortError: vi.fn(() => false),
  listReports: vi.fn(),
}))

let mockUser: { id: string; email: string } | null = { id: 'user-1', email: 'user@example.com' }

vi.mock('@/lib/auth/useAuth', () => ({
  useAuth: () => ({
    user: mockUser,
  }),
}))

function paginated(
  items: Array<{ id: string; query: string; created_at: string; competitor_count: number }>,
  hasNext = false,
) {
  return { items, total: items.length, has_next: hasNext, limit: 20, offset: 0 }
}

describe('HistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    window.sessionStorage.clear()
    mockUser = { id: 'user-1', email: 'user@example.com' }
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
      .mockResolvedValueOnce(paginated(firstPage, true))
      .mockResolvedValueOnce(paginated(secondPage, false))
      .mockResolvedValueOnce(paginated(firstPage, true))

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
      .mockResolvedValueOnce(paginated(firstPage, true))
      .mockResolvedValueOnce(paginated([], false))
      .mockResolvedValueOnce(paginated(firstPage, false))
      .mockResolvedValue(paginated(firstPage, false))

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
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled()
    })
  })

  it('opens a shared dialog and closes it from cancel actions', async () => {
    vi.mocked(listReports).mockResolvedValueOnce(
      paginated([
        {
          id: 'report-1',
          query: 'AI meeting notes',
          created_at: new Date().toISOString(),
          competitor_count: 3,
        },
      ]),
    )

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

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /delete report/i }))

    const dialog = await screen.findByRole('dialog', { name: /delete this report/i })
    expect(dialog).toHaveAttribute('aria-describedby')

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('renders cached history immediately while refreshing in the background', async () => {
    window.sessionStorage.setItem(HISTORY_CACHE_STORAGE_KEY, JSON.stringify({
      userId: 'user-1',
      pageIndex: 0,
      limit: 20,
      hasNextPage: false,
      total: 1,
      reports: [
        {
          id: 'cached-report',
          query: 'Cached report',
          created_at: new Date().toISOString(),
          competitor_count: 5,
        },
      ],
    }))

    vi.mocked(listReports).mockImplementation(
      () =>
        new Promise(() => {
          // keep request pending so the test only observes initial paint
        }),
    )

    render(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports/:id" element={<div>REPORT PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('Cached report')).toBeInTheDocument()
  })

  it('hydrates cached history after auth bootstrap completes', async () => {
    window.sessionStorage.setItem(HISTORY_CACHE_STORAGE_KEY, JSON.stringify({
      userId: 'user-1',
      pageIndex: 0,
      limit: 20,
      hasNextPage: false,
      total: 1,
      reports: [
        {
          id: 'cached-report',
          query: 'Hydrated cached history',
          created_at: new Date().toISOString(),
          competitor_count: 5,
        },
      ],
    }))
    mockUser = null

    vi.mocked(listReports).mockImplementation(
      () =>
        new Promise(() => {
          // keep pending so the test only observes cache hydration
        }),
    )

    const { rerender } = render(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports/:id" element={<div>REPORT PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.queryByText('Hydrated cached history')).not.toBeInTheDocument()

    mockUser = { id: 'user-1', email: 'user@example.com' }
    rerender(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports/:id" element={<div>REPORT PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('Hydrated cached history')).toBeInTheDocument()
  })

  it('ignores cached history snapshots when the page size contract changes', async () => {
    window.sessionStorage.setItem(HISTORY_CACHE_STORAGE_KEY, JSON.stringify({
      userId: 'user-1',
      pageIndex: 0,
      limit: 5,
      hasNextPage: false,
      total: 20,
      reports: Array.from({ length: 5 }, (_, index) => ({
        id: `cached-${index + 1}`,
        query: `Cached report ${index + 1}`,
        created_at: new Date().toISOString(),
        competitor_count: 2,
      })),
    }))

    vi.mocked(listReports).mockImplementation(() => new Promise(() => {}))

    render(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports/:id" element={<div>REPORT PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.queryByText('Cached report 1')).not.toBeInTheDocument()
    expect(document.querySelectorAll('.animate-pulse')).toHaveLength(4)
  })

  it('keeps the search input visible when a query returns zero matches', async () => {
    vi.mocked(listReports)
      .mockResolvedValueOnce(
        paginated([
          {
            id: 'report-1',
            query: 'AI meeting notes',
            created_at: new Date().toISOString(),
            competitor_count: 3,
          },
        ]),
      )
      .mockResolvedValueOnce(paginated([], false))

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

    fireEvent.change(
      screen.getByRole('textbox', { name: /search your past reports/i }),
      { target: { value: 'missing report' } },
    )

    await waitFor(() => {
      expect(screen.getByText(/couldn't find any reports matching/i)).toBeInTheDocument()
    })

    expect(
      screen.getByRole('textbox', { name: /search your past reports/i }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/haven't run any research reports yet/i)).not.toBeInTheDocument()
  })

  it('shows an error state instead of the empty state when history loading fails', async () => {
    vi.mocked(listReports).mockRejectedValueOnce(new Error('Report store unavailable'))

    render(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports/:id" element={<div>REPORT PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Report store unavailable')).toBeInTheDocument()
    })
    expect(screen.queryByText(/no reports yet/i)).not.toBeInTheDocument()
  })

  it('clears stale history errors after the signed-in user disappears', async () => {
    vi.mocked(listReports).mockRejectedValueOnce(new Error('Report store unavailable'))

    const { rerender } = render(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports/:id" element={<div>REPORT PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Report store unavailable')).toBeInTheDocument()
    })

    mockUser = null
    rerender(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports/:id" element={<div>REPORT PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.queryByText('Report store unavailable')).not.toBeInTheDocument()
    })
  })
})
