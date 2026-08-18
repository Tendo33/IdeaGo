-- Migration 019: schedulable cleanup for revocable auth sessions.
--
-- `auth_sessions` had no retention story at all: every LinuxDo login inserted a
-- row and nothing ever removed one, so the table grew for the life of the
-- deployment. Migrations 010/011/012 shipped cleanup functions for
-- processed_webhook_events, rate_limit_hits and audit_log, but nothing in the
-- application ever called them either — see the periodic maintenance task in
-- src/ideago/api/app.py, which now invokes all of them.

CREATE OR REPLACE FUNCTION public.cleanup_auth_sessions(
  p_max_age_hours int DEFAULT 720,
  p_revoked_grace_hours int DEFAULT 24
)
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_count int;
  v_total int := 0;
BEGIN
  -- Revoked sessions are kept briefly so an in-flight request still sees the
  -- revocation rather than a missing row (a missing row is also treated as
  -- inactive, but keeping it makes the intent auditable for a short window).
  DELETE FROM public.auth_sessions
    WHERE revoked_at IS NOT NULL
      AND revoked_at < now() - make_interval(hours => p_revoked_grace_hours);
  GET DIAGNOSTICS v_count = ROW_COUNT;
  v_total := v_total + v_count;

  -- Sessions older than the maximum token lifetime can never authenticate
  -- again, so the row has no purpose.
  DELETE FROM public.auth_sessions
    WHERE created_at < now() - make_interval(hours => p_max_age_hours);
  GET DIAGNOSTICS v_count = ROW_COUNT;
  v_total := v_total + v_count;

  RETURN v_total;
END;
$$;

COMMENT ON FUNCTION public.cleanup_auth_sessions IS
  'Removes revoked and expired custom auth sessions. Called from the backend periodic maintenance task.';
