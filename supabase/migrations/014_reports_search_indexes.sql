-- Migration 014: Improve report history pagination and fuzzy search performance.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_reports_user_created_at
  ON public.reports (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_reports_query_trgm
  ON public.reports
  USING gin (query gin_trgm_ops);
