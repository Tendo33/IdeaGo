-- Migration 017: revocable custom auth sessions, profile tombstones, and report indexes.

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS deletion_pending boolean NOT NULL DEFAULT false;

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_profiles_active_created_at_desc
  ON public.profiles (created_at DESC)
  WHERE deletion_pending = false AND deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_reports_user_created_at_desc
  ON public.reports (user_id, created_at DESC);

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_reports_query_trgm
  ON public.reports
  USING gin (query gin_trgm_ops);

CREATE TABLE IF NOT EXISTS public.auth_sessions (
  session_id text PRIMARY KEY,
  user_id uuid NOT NULL,
  provider text NOT NULL DEFAULT 'linuxdo',
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_created_at
  ON public.auth_sessions (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_active
  ON public.auth_sessions (user_id, revoked_at)
  WHERE revoked_at IS NULL;

ALTER TABLE public.auth_sessions ENABLE ROW LEVEL SECURITY;
