import { createContext } from 'react'

export interface AuthSessionUser {
  id: string
  email: string
}

export interface AuthSession {
  access_token: string
  provider: string
  user: AuthSessionUser
}

export interface AuthContextType {
  session: AuthSession | null
  user: AuthSessionUser | null
  loading: boolean
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextType | null>(null)
