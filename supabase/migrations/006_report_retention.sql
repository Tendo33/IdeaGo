-- Migration 006: SaaS report retention.
--
-- User-owned reports should persist indefinitely (or per plan policy).
-- Only anonymous / unowned reports expire via TTL.
--
-- Adds `expires_at` column and rewrites cleanup_expired_reports to use it.

-- 1. Add nullable expires_at column (NULL = never expires)
ALTER TABLE public.reports
  ADD COLUMN IF NOT EXISTS expires_at timestamptz;

-- 2. Backfill: mark existing user-owned reports as non-expiring,
--    and set a 24h expiry for unowned reports.
UPDATE public.reports
  SET expires_at = NULL
  WHERE user_id IS NOT NULL;

UPDATE public.reports
  SET expires_at = created_at + interval '24 hours'
  WHERE user_id IS NULL AND expires_at IS NULL;

-- 3. Index for cleanup query
CREATE INDEX IF NOT EXISTS idx_reports_expires_at
  ON public.reports (expires_at)
  WHERE expires_at IS NOT NULL;

-- 4. Replace cleanup function to use expires_at instead of blanket TTL
CREATE OR REPLACE FUNCTION public.cleanup_expired_reports(p_ttl_hours int default 24)
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_count int;
BEGIN
  DELETE FROM public.reports
    WHERE expires_at IS NOT NULL
      AND expires_at < now();
  GET DIAGNOSTICS v_count = ROW_COUNT;

  DELETE FROM public.report_status
    WHERE updated_at < now() - make_interval(hours => p_ttl_hours)
      AND user_id IS NULL;

  RETURN v_count;
END;
$$;
