-- PG-backed rate limiter for multi-process / multi-node deployments.
-- Replaces the in-memory sliding-window rate limiter.

CREATE TABLE IF NOT EXISTS public.rate_limit_hits (
  key     text        NOT NULL,
  hit_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_hits_key_time
  ON public.rate_limit_hits (key, hit_at);

ALTER TABLE public.rate_limit_hits ENABLE ROW LEVEL SECURITY;

-- Atomic sliding-window check: returns TRUE when the request should be REJECTED.
CREATE OR REPLACE FUNCTION public.check_rate_limit(
  p_key            text,
  p_max_requests   int,
  p_window_seconds int
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  cutoff    timestamptz;
  hit_count int;
BEGIN
  cutoff := now() - make_interval(secs => p_window_seconds);

  DELETE FROM rate_limit_hits WHERE key = p_key AND hit_at < cutoff;

  SELECT count(*) INTO hit_count
    FROM rate_limit_hits
   WHERE key = p_key AND hit_at >= cutoff;

  IF hit_count >= p_max_requests THEN
    RETURN true;
  END IF;

  INSERT INTO rate_limit_hits (key, hit_at) VALUES (p_key, now());
  RETURN false;
END;
$$;

-- Periodic cleanup of very old rows (called by cron or app-level task).
CREATE OR REPLACE FUNCTION public.cleanup_rate_limit_hits(p_max_age_seconds int DEFAULT 7200)
RETURNS int
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  removed int;
BEGIN
  DELETE FROM rate_limit_hits
   WHERE hit_at < now() - make_interval(secs => p_max_age_seconds);
  GET DIAGNOSTICS removed = ROW_COUNT;
  RETURN removed;
END;
$$;
