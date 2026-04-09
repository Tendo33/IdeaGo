-- Migration 016: support admin sorting and profile inspection paths.

CREATE INDEX IF NOT EXISTS idx_profiles_created_at_desc
  ON public.profiles (created_at DESC);
