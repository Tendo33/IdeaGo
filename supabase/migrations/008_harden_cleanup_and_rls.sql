-- Migration 008: Security hardening — cleanup guard + processing_reports RLS.
--
-- 1. Harden cleanup_expired_reports to never delete user-owned reports.
--    The previous function relied solely on expires_at. If a bug leaves
--    expires_at non-NULL on a user-owned report, the function would delete it.
--    Adding an explicit user_id IS NULL guard provides defense-in-depth.
--
-- 2. Enable RLS on processing_reports. This table was created in migration 005
--    without RLS, meaning anyone with the anon key could query/mutate it.
--    Only service_role (backend) should access this table.

-- ── Part 1: Harden cleanup function ──────────────────────────

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
      AND expires_at < now()
      AND user_id IS NULL;
  GET DIAGNOSTICS v_count = ROW_COUNT;

  DELETE FROM public.report_status
    WHERE updated_at < now() - make_interval(hours => p_ttl_hours)
      AND user_id IS NULL;

  RETURN v_count;
END;
$$;

-- ── Part 2: Lock down processing_reports ─────────────────────

ALTER TABLE public.processing_reports ENABLE ROW LEVEL SECURITY;

-- No SELECT/INSERT/UPDATE/DELETE policies for anon or authenticated roles.
-- Only service_role (which bypasses RLS) can access this table.
