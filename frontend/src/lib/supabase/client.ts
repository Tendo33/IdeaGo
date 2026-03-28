import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string
const MISSING_SUPABASE_ENV_MESSAGE =
  'Supabase URL or anon key is missing — auth will not work.'

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(MISSING_SUPABASE_ENV_MESSAGE)
}

type SupabaseClientType = ReturnType<typeof createClient>

function createFallbackSupabaseClient(): SupabaseClientType {
  const authError = () => new Error(MISSING_SUPABASE_ENV_MESSAGE)

  return {
    auth: {
      signOut: async () => ({ error: null }),
      getSession: async () => ({ data: { session: null }, error: null }),
      onAuthStateChange: () => ({
        data: {
          subscription: {
            unsubscribe() {},
          },
        },
      }),
      signInWithOAuth: async () => ({
        data: { provider: null, url: null },
        error: authError(),
      }),
      signInWithPassword: async () => ({
        data: { user: null, session: null },
        error: authError(),
      }),
      signUp: async () => ({
        data: { user: null, session: null },
        error: authError(),
      }),
      resetPasswordForEmail: async () => ({
        data: {},
        error: authError(),
      }),
      updateUser: async () => ({
        data: { user: null },
        error: authError(),
      }),
    },
  } as unknown as SupabaseClientType
}

export const supabase =
  supabaseUrl && supabaseAnonKey
    ? createClient(supabaseUrl, supabaseAnonKey)
    : createFallbackSupabaseClient()
