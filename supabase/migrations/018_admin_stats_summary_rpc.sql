-- Migration 018: Aggregate admin stats summary RPC.

CREATE OR REPLACE FUNCTION public.get_admin_stats_summary()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER SET search_path = ''
AS $$
  WITH plan_rows AS (
    SELECT
      COALESCE(NULLIF(p.plan, ''), 'free') AS plan,
      COUNT(*)::int AS count
    FROM public.profiles p
    GROUP BY COALESCE(NULLIF(p.plan, ''), 'free')
  ),
  plan_breakdown AS (
    SELECT COALESCE(jsonb_object_agg(plan, count), '{}'::jsonb) AS payload
    FROM plan_rows
  )
  SELECT jsonb_build_object(
    'total_users', (SELECT COUNT(*)::int FROM public.profiles),
    'total_reports', (SELECT COUNT(*)::int FROM public.reports),
    'active_processing', (SELECT COUNT(*)::int FROM public.processing_reports),
    'plan_breakdown', (SELECT payload FROM plan_breakdown)
  );
$$;
