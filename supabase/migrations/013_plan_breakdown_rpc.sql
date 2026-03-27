-- Migration 013: Aggregate plan breakdown RPC for admin stats dashboard.

CREATE OR REPLACE FUNCTION public.get_plan_breakdown()
RETURNS TABLE(plan text, count int)
LANGUAGE sql
STABLE
SECURITY DEFINER SET search_path = ''
AS $$
  SELECT
    COALESCE(NULLIF(p.plan, ''), 'free') AS plan,
    COUNT(*)::int AS count
  FROM public.profiles p
  GROUP BY COALESCE(NULLIF(p.plan, ''), 'free')
  ORDER BY count DESC;
$$;
