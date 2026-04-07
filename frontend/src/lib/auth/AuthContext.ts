import { createContext } from 'react'

export interface AuthSessionUser {
  id: string
  email: string
  display_name?: string
}

export interface AuthSession {
  access_token: string
  provider: string
  user: AuthSessionUser
}

export interface AuthContextType {
  session: AuthSession | null
  user: AuthSessionUser | null
  role: string
  loading: boolean
  roleLoading: boolean
  signOut: () => Promise<void>
  applyCustomSession: (session: AuthSession) => void
  patchUser: (updates: Partial<AuthSessionUser>) => void
}

export const AuthContext = createContext<AuthContextType | null>(null)

function trimOrEmpty(value: string | undefined): string {
  return typeof value === 'string' ? value.trim() : ''
}

export function getUserDisplayName(user: AuthSessionUser | null | undefined, fallback = 'User'): string {
  const displayName = trimOrEmpty(user?.display_name)
  if (displayName) return displayName

  const email = trimOrEmpty(user?.email)
  if (!email) return fallback

  const [localPart] = email.split('@')
  return localPart || email || fallback
}

export function getUserInitial(user: AuthSessionUser | null | undefined, fallback = 'U'): string {
  return getUserDisplayName(user, fallback).charAt(0).toUpperCase() || fallback
}

export function truncateMiddle(value: string, maxLength = 40): string {
  if (value.length <= maxLength) return value
  if (maxLength <= 1) return value.slice(0, maxLength)

  const visible = maxLength - 1
  const left = Math.ceil(visible * 0.6)
  const right = Math.max(0, visible - left)
  return `${value.slice(0, left)}…${value.slice(value.length - right)}`
}
