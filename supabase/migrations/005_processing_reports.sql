-- Migration 005: Persistent processing_reports table for distributed dedup.
--
-- Replaces the in-memory _processing_reports dict so that multiple workers /
-- containers share the same dedup state.  Each row represents a pipeline
-- slot currently being processed.  Rows are removed when the pipeline
-- completes, fails, or is cancelled.
--
-- A stale-row safety net is provided: rows older than 30 minutes are
-- considered abandoned and ignored / cleaned up.

CREATE TABLE IF NOT EXISTS public.processing_reports (
  key            text        PRIMARY KEY,
  report_id      text        NOT NULL,
  user_id        text        NOT NULL DEFAULT '',
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_processing_reports_report_id
  ON public.processing_reports (report_id);

-- Atomically reserve a processing slot.
-- Returns NULL if the slot was successfully reserved (new row inserted).
-- Returns the existing report_id if the slot was already taken.
-- Ignores rows older than 30 minutes (stale safety net).
CREATE OR REPLACE FUNCTION public.reserve_processing_slot(
  p_key       text,
  p_report_id text,
  p_user_id   text DEFAULT ''
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_existing text;
BEGIN
  -- Clean up stale row for this key (older than 30 min)
  DELETE FROM public.processing_reports
    WHERE key = p_key
      AND created_at < now() - interval '30 minutes';

  -- Try to read existing (non-stale) reservation
  SELECT report_id INTO v_existing
    FROM public.processing_reports
    WHERE key = p_key;

  IF v_existing IS NOT NULL THEN
    RETURN v_existing;
  END IF;

  -- Reserve the slot
  INSERT INTO public.processing_reports (key, report_id, user_id)
    VALUES (p_key, p_report_id, p_user_id)
    ON CONFLICT (key) DO NOTHING;

  -- Check if we won the race
  SELECT report_id INTO v_existing
    FROM public.processing_reports
    WHERE key = p_key;

  IF v_existing = p_report_id THEN
    RETURN NULL;  -- successfully reserved
  END IF;

  RETURN v_existing;  -- someone else got there first
END;
$$;

-- Release all slots for a given report_id.
CREATE OR REPLACE FUNCTION public.release_processing_slot(p_report_id text)
RETURNS void
LANGUAGE sql
SECURITY DEFINER SET search_path = ''
AS $$
  DELETE FROM public.processing_reports WHERE report_id = p_report_id;
$$;

-- Check if a report_id is currently processing.
CREATE OR REPLACE FUNCTION public.is_report_processing(p_report_id text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER SET search_path = ''
AS $$
  SELECT EXISTS(
    SELECT 1 FROM public.processing_reports
      WHERE report_id = p_report_id
        AND created_at >= now() - interval '30 minutes'
  );
$$;

-- Periodic cleanup: remove all stale slots older than 30 minutes.
CREATE OR REPLACE FUNCTION public.cleanup_stale_processing_slots()
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_count int;
BEGIN
  DELETE FROM public.processing_reports
    WHERE created_at < now() - interval '30 minutes';
  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END;
$$;
