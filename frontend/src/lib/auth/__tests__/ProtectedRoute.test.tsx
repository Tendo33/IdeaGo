import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminRoute } from '../ProtectedRoute'

const authState = vi.hoisted(() => ({
  user: { id: 'admin-1', email: 'admin@example.com' },
  role: 'user',
  loading: false,
  roleLoading: false,
}))

vi.mock('../useAuth', () => ({
  useAuth: () => ({
    session: authState.user ? { user: authState.user, access_token: 'tok' } : null,
    user: authState.user,
    role: authState.role,
    loading: authState.loading,
    roleLoading: authState.roleLoading,
    signOut: vi.fn(),
    applyCustomSession: vi.fn(),
    patchUser: vi.fn(),
  }),
}))

describe('AdminRoute', () => {
  beforeEach(() => {
    authState.user = { id: 'admin-1', email: 'admin@example.com' }
    authState.role = 'user'
    authState.loading = false
    authState.roleLoading = false
  })

  it('keeps showing the loading state while role hydration is in flight', () => {
    authState.roleLoading = true

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <AdminRoute>
          <div>ADMIN PAGE</div>
        </AdminRoute>
      </MemoryRouter>,
    )

    expect(screen.getByText('Loading page content...')).toBeInTheDocument()
    expect(screen.queryByText('Access Denied')).not.toBeInTheDocument()
    expect(screen.queryByText('ADMIN PAGE')).not.toBeInTheDocument()
  })
})
