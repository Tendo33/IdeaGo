-- Migration 010: Stripe webhook idempotency table.
--
-- Records processed Stripe event IDs to prevent duplicate handling.
-- Old entries are cleaned up after 72 hours.

CREATE TABLE IF NOT EXISTS public.processed_webhook_events (
  event_id    text        PRIMARY KEY,
  event_type  text        NOT NULL DEFAULT '',
  processed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_processed_webhook_events_processed_at
  ON public.processed_webhook_events (processed_at);

ALTER TABLE public.processed_webhook_events ENABLE ROW LEVEL SECURITY;

-- Cleanup function: remove events older than 72 hours
CREATE OR REPLACE FUNCTION public.cleanup_old_webhook_events()
RETURNS int
LANGUAGE sql
SECURITY DEFINER SET search_path = ''
AS $$
  WITH deleted AS (
    DELETE FROM public.processed_webhook_events
      WHERE processed_at < now() - interval '72 hours'
    RETURNING 1
  )
  SELECT count(*)::int FROM deleted;
$$;
